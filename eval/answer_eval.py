# eval/answer_eval.py
"""Answer evaluation: every question in eval/questions.jsonl, in simple and in agent mode.

Two steps, so the LLM is asked each (question, mode) only once:
  run    asks the questions and appends each raw result to eval/results/answers_raw.jsonl
         right away. It skips pairs already saved, so after a crash or a stop you run the same
         command again and it carries on. An answer that failed because the LLM gave up
         (LLMUnavailable) is saved as an error and asked again on the next run.
  score  reads the raw file and computes every metric. No LLM and no database, so you can
         rerun it as often as you like, for example after fixing a metric.

Run from the repo root:
  python -m eval.answer_eval run --limit 2    # smoke test: first 2 questions, both modes
  python -m eval.answer_eval run              # everything still missing (about 20-30 minutes)
  python -m eval.answer_eval run .env.neon    # the same against the database in .env.neon
  python -m eval.answer_eval score            # writes the result files in eval/results/
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from eval.metrics import citation_accuracy, exact_match, gold_in_answer, mrr, recall_at_k, token_f1

QUESTIONS_PATH = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")
RAW_PATH = RESULTS_DIR / "answers_raw.jsonl"
SCORES_PATH = RESULTS_DIR / "answer_scores.jsonl"
TABLE_PATH = RESULTS_DIR / "answers.md"
GRADING_PATH = RESULTS_DIR / "company_answers_for_grading.md"

MODES = ("simple", "agent")
RECALL_K = 5
MRR_DEPTH = 8                # simple mode sends 8 sources to the LLM; agent mode is cut to the same depth
PAUSE_SECONDS = 4.0          # between questions, to stay under the free tier's requests-per-minute limit
MAX_ERRORS_IN_A_ROW = 3      # this many failed answers in a row usually means the quota is used up
AGENT_TITLES_KEY = "document_titles"  # the key in each trace["searches"] item that holds the document titles
TYPE_ORDER = ["bridge", "comparison", "simple", "multi_doc", "contradiction", "unanswerable"]
STATUS_ORDER = ["answered", "partial", "insufficient", "error"]
MARKERS = re.compile(r"\[S\d+(?:\s*,\s*S\d+)*\]")   # [S1] or [S1, S3], as in app/answer.py


# ---------------------------------------------------------------- helpers

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_records(records: list[dict]) -> dict[tuple[str, str], dict]:
    """The last saved record per (question id, mode): a retry replaces an earlier error."""
    return {(r["id"], r["mode"]): r for r in records}


def strip_markers(text: str) -> str:
    """'Paris [S1][S3] is big.' -> 'Paris   is big.' The answer metrics should only see words."""
    return MARKERS.sub(" ", text)


def unique_in_order(titles: list[str]) -> list[str]:
    """Drop repeated titles but keep the order: a document's rank is where it first appears."""
    return list(dict.fromkeys(titles))


def agent_titles(trace: dict) -> list[str]:
    """Titles from all of the agent's searches, in the order it saw them (the Day 3 rule)."""
    titles = []
    for search in trace.get("searches", []):
        if AGENT_TITLES_KEY not in search:
            raise KeyError(
                f"trace['searches'] items have the keys {sorted(search)}, not {AGENT_TITLES_KEY!r}. "
                "Set AGENT_TITLES_KEY in eval/answer_eval.py to the key that holds the document titles, "
                "then run score again (the saved results stay valid)."
            )
        titles.extend(search[AGENT_TITLES_KEY])
    return titles


def retrieved_ranking(record: dict) -> list[str]:
    """Document titles in the order the mode saw them. Agent titles are read from the saved trace
    here rather than at run time, so a wrong AGENT_TITLES_KEY never costs LLM calls."""
    if record["mode"] == "agent":
        return agent_titles(record["trace"]) if record["trace"] else []
    return record["retrieved_titles"]


# ---------------------------------------------------------------- run: ask the questions

def run_one(question: dict, mode: str) -> dict:
    """Ask one question in one mode and return the raw record that gets saved."""
    # Imported here, not at the top, so that `score` works without a database or an API key.
    from app import config, db
    from app.agent import run_agent
    from app.answer import TOP_K, answer_question
    from app.llm import LLMUnavailable
    from app.search import hybrid_search

    retrieved, trace, error = [], None, None
    with db.get_conn() as conn:
        if mode == "simple":
            # answer_question() runs this same search first, but its answer only lists the
            # chunks it cited. Recall and MRR need the whole ranking, so we search once more.
            retrieved = [row["document_title"] for row in hybrid_search(conn, question["question"], TOP_K)]
        start = time.perf_counter()
        try:
            if mode == "simple":
                answer = answer_question(conn, question["question"])
            else:
                answer, trace = run_agent(conn, question["question"])
        except LLMUnavailable as failure:   # gave up after retries, or two unreadable replies
            error = str(failure)
            answer = {"status": "error", "answer": "", "citations": [], "conflicts": [], "missing": []}
        seconds = time.perf_counter() - start

    record = {
        "id": question["id"],
        "mode": mode,
        "question": question["question"],
        "answer": answer,
        "retrieved_titles": retrieved,   # simple mode only; agent titles come from the trace
        "trace": trace,
        "seconds": round(seconds, 2),
        "model": config.GEMINI_MODEL,
        "database": os.getenv("ENV_FILE", ".env"),
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if error:
        record["error"] = error
    return record


def run(limit: int | None, modes: list[str], pause: float) -> None:
    from app import db
    from app.search import hybrid_search

    questions = load_jsonl(QUESTIONS_PATH)
    if not questions:
        sys.exit(f"{QUESTIONS_PATH} is missing or empty. Run: python -m scripts.build_eval_questions")
    if limit:
        questions = questions[:limit]
    saved = latest_records(load_jsonl(RAW_PATH))
    done = {pair for pair, record in saved.items() if "error" not in record}
    todo = [(q, mode) for q in questions for mode in modes if (q["id"], mode) not in done]
    print(f"{len(questions)} questions x {len(modes)} modes: {len(todo)} to run, the rest already saved")
    if not todo:
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with db.get_conn() as conn:
        hybrid_search(conn, "warm-up", 1)  # loads the embedding model now, so it isn't timed

    errors, errors_in_a_row = 0, 0
    for n, (q, mode) in enumerate(todo, start=1):
        record = run_one(q, mode)
        with RAW_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        status = record["answer"]["status"]
        print(f"[{n:>3}/{len(todo)}] {q['id']:<16} {mode:<6} {status:<12} {record['seconds']:5.1f} s"
              + (f"  ({record['error']})" if "error" in record else ""))
        if "error" in record:
            errors += 1
            errors_in_a_row += 1
            if errors_in_a_row >= MAX_ERRORS_IN_A_ROW:
                sys.exit(
                    f"\nStopped: {MAX_ERRORS_IN_A_ROW} answers in a row failed. Everything so far is saved.\n"
                    "Wait a few minutes and run the same command again; it continues and retries the failed ones. "
                    "If the daily quota is used up, switch GEMINI_MODEL to your backup model first."
                )
        else:
            errors_in_a_row = 0
        if n < len(todo):
            time.sleep(pause)
    print(f"Done. Raw results: {RAW_PATH}")
    if errors:
        print(f"{errors} answers failed and were saved as errors. Run the same command again to retry only those.")


# ---------------------------------------------------------------- score: compute the metrics

def score_one(q: dict, record: dict) -> dict:
    """All metrics for one question in one mode. A metric that doesn't apply is left out."""
    answer = record["answer"]
    row = {
        "id": q["id"], "mode": record["mode"], "source": q["source"], "type": q["type"],
        "expected": q["expected"], "status": answer["status"], "seconds": record["seconds"],
    }
    gold = q["gold_titles"]
    failed_agent = "error" in record and record["mode"] == "agent"   # no trace, so nothing to rank
    if gold and not failed_agent:       # unanswerable questions have nothing to retrieve
        ranked = unique_in_order(retrieved_ranking(record))
        row["recall@5"] = recall_at_k(ranked, gold, RECALL_K)
        row["mrr"] = mrr(ranked[:MRR_DEPTH], gold)
        row["evidence_recall"] = recall_at_k(ranked, gold, len(ranked))
    if gold:
        cited = [c["document_title"] for c in answer["citations"]]
        row["citation_accuracy"] = citation_accuracy(cited, gold + q.get("acceptable_titles", []))
    if q["source"] == "hotpotqa":       # an error has no answer text, so it scores 0 here
        prediction = strip_markers(answer["answer"])
        row["em"] = exact_match(prediction, q["gold_answer"])
        row["f1"] = token_f1(prediction, q["gold_answer"])
        row["gold_in_answer"] = gold_in_answer(prediction, q["gold_answer"])
    row["abstained"] = answer["status"] == "insufficient"
    row["conflict_reported"] = bool(answer["conflicts"])
    if record["trace"]:
        row["rounds"] = record["trace"].get("rounds")
        row["fallback"] = record["trace"].get("fallback")
    return row


def mean(rows: list[dict], key: str) -> tuple[float | None, int]:
    """Average of a metric over the rows that have it (None values skipped), and how many there were."""
    values = [r[key] for r in rows if r.get(key) is not None]
    return (sum(values) / len(values), len(values)) if values else (None, 0)


def count(rows: list[dict], key: str, where) -> str:
    """'4/5': rows where `key` is true, out of the rows matching `where`."""
    matching = [r for r in rows if where(r)]
    return f"{sum(1 for r in matching if r[key])}/{len(matching)}" if matching else "–"


def fmt(value: float | None, digits: int = 3) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


MEAN_METRICS = [
    ("Recall@5 (documents)", "recall@5"),
    (f"MRR (first {MRR_DEPTH} documents)", "mrr"),
    ("Evidence recall (every document the mode saw)", "evidence_recall"),
    ("Citation accuracy", "citation_accuracy"),
    ("Exact match (HotpotQA)", "em"),
    ("Token F1 (HotpotQA)", "f1"),
    ("Gold answer in the answer (HotpotQA)", "gold_in_answer"),
]
COUNT_METRICS = [
    ("Abstained on unanswerable questions", "abstained", lambda r: r["expected"] == "insufficient"),
    ("Wrongly abstained on answerable questions", "abstained", lambda r: r["expected"] != "insufficient"),
    ("Reported a conflict on contradiction questions", "conflict_reported", lambda r: r["expected"] == "flag_conflict"),
    ("Reported a conflict on other answerable questions", "conflict_reported", lambda r: r["expected"] == "answer"),
]


def overall_table(by_mode: dict[str, list[dict]]) -> list[str]:
    lines = ["| Metric | Scored (simple / agent) | simple | agent |", "| --- | ---: | ---: | ---: |"]
    for label, key in MEAN_METRICS:
        results = {mode: mean(rows, key) for mode, rows in by_mode.items()}
        scored = " / ".join(str(results[m][1]) for m in MODES)
        lines.append(f"| {label} | {scored} | " + " | ".join(fmt(results[m][0]) for m in MODES) + " |")
    for label, key, where in COUNT_METRICS:
        lines.append(f"| {label} | | " + " | ".join(count(by_mode[m], key, where) for m in MODES) + " |")
    statuses = {m: Counter(r["status"] for r in by_mode[m]) for m in MODES}
    lines.append(f"| Status: {' / '.join(STATUS_ORDER)} | | " + " | ".join(
        " / ".join(str(statuses[m][s]) for s in STATUS_ORDER) for m in MODES) + " |")
    lines.append("| Average seconds per question | | " + " | ".join(fmt(mean(by_mode[m], 'seconds')[0], 1) for m in MODES) + " |")
    agent = by_mode["agent"]
    fallbacks = sum(1 for r in agent if r.get("fallback"))
    lines.append(f"| Agent: average rounds, fallbacks | | – | {fmt(mean(agent, 'rounds')[0], 1)}, {fallbacks} |")
    return lines


def type_table(by_mode: dict[str, list[dict]]) -> list[str]:
    columns = [("Recall@5", "recall@5"), ("Evidence recall", "evidence_recall"),
               ("Citation acc.", "citation_accuracy"), ("Token F1", "f1")]
    lines = [
        "| Type | Questions | " + " | ".join(f"{label} (s / a)" for label, _ in columns) + " | Abstained (s / a) |",
        "| --- | ---: | " + " | ".join("---:" for _ in columns) + " | ---: |",
    ]
    for kind in TYPE_ORDER:
        rows = {m: [r for r in by_mode[m] if r["type"] == kind] for m in MODES}
        if not rows["simple"] and not rows["agent"]:
            continue
        cells = [" / ".join(fmt(mean(rows[m], key)[0], 2) for m in MODES) for _, key in columns]
        abstained = " / ".join(count(rows[m], "abstained", lambda r: True) for m in MODES)
        lines.append(f"| {kind} | {max(len(rows['simple']), len(rows['agent']))} | " + " | ".join(cells) + f" | {abstained} |")
    return lines


def results_markdown(questions: list[dict], by_mode: dict[str, list[dict]], records: list[dict]) -> str:
    models = sorted({r["model"] for r in records})
    databases = sorted({r["database"] for r in records})
    sources = Counter(q["source"] for q in questions)
    lines = [
        "# Answer evaluation: simple vs agent mode",
        "",
        f"{len(questions)} questions from `{QUESTIONS_PATH.as_posix()}` ({sources['hotpotqa']} HotpotQA, "
        f"{sources['company']} NovaPay), each answered once per mode. Model: {', '.join(models)}. "
        f"Database: {', '.join(databases)}. Generated by `python -m eval.answer_eval score` on {date.today().isoformat()}.",
    ]
    if len(models) > 1:
        lines += ["", "**Warning:** the results come from more than one model (the run switched models part-way)."]
    lines += ["", "## Overall", "", *overall_table(by_mode), "", "## By question type", "",
              "s = simple mode, a = agent mode.", "", *type_table(by_mode), "",
              "## How each number is computed", "",
              "- **Retrieval** compares document titles. Each document counts once, at the position where it first "
              "appears. Simple mode's ranking is its hybrid search for the question (top 8 chunks); agent mode's is "
              "every document its searches returned, in the order it saw them.",
              f"- **Recall@{RECALL_K}**: share of the gold documents among the first {RECALL_K} documents. "
              "**Evidence recall**: the same over every document the mode saw, which is where extra agent searches can help. "
              f"**MRR**: 1 / rank of the first gold document within the first {MRR_DEPTH}, averaged.",
              "- **Citation accuracy**: of the documents an answer cites, the share that are gold (or also state the "
              "fact, for NovaPay questions). Answers that cite nothing are not scored, so the Scored column can differ.",
              "- **Exact match / Token F1** use SQuAD-style normalization after removing the [S#] markers. The answers "
              "are full sentences, so exact match is close to 0 by design; **Gold answer in the answer** checks whether "
              "the normalized gold answer appears in the answer as whole words.",
              "- **Abstained** means status `insufficient`. **Reported a conflict** means the `conflicts` list is not "
              "empty; whether it is the right conflict is graded by hand.",
              "- **error** means the LLM call failed even after retries; it counts as a wrong answer, and agent-mode "
              "errors have no retrieval scores because their search trace was lost.",
              ""]
    return "\n".join(lines)


def grading_markdown(questions: list[dict], latest: dict[tuple[str, str], dict]) -> str:
    """The NovaPay answers side by side, ready for hand grading."""
    lines = ["# NovaPay answers for hand grading", "",
             "For each answer write: correct / partly correct / wrong, and for contradiction questions "
             "whether the conflict was flagged (yes / no).", ""]
    for q in questions:
        if q["source"] != "company":
            continue
        lines += [f"## {q['id']} · {q['type']} · expected: {q['expected']}", "",
                  f"**Question:** {q['question']}", "",
                  f"**Reference:** {q['gold_answer']}", "",
                  f"**Gold documents:** {', '.join(q['gold_titles']) or '(none)'}", ""]
        for mode in MODES:
            record = latest.get((q["id"], mode))
            if record is None:
                lines += [f"### {mode}: no result yet", ""]
                continue
            a = record["answer"]
            cited = unique_in_order([c["document_title"] for c in a["citations"]])
            lines += [f"### {mode}: {a['status']}", "", a["answer"] or "(no answer text)", "",
                      f"- Cited: {', '.join(cited) or '(nothing)'}"]
            if "error" in record:
                lines.append(f"- Error: {record['error']}")
            for conflict in a["conflicts"]:
                claims = " vs ".join(
                    f"{p.get('claim', '?')} ({', '.join(str(s) for s in p.get('sources', []))})"
                    for p in conflict.get("positions", [])
                )
                lines.append(f"- Conflict, {conflict.get('topic', '?')}: {claims}")
            if a["missing"]:
                lines.append(f"- Missing: {'; '.join(str(m) for m in a['missing'])}")
            grade = "- **Grade:** ___"
            if q["expected"] == "flag_conflict":
                grade += " · **Conflict flagged:** ___"
            lines += [grade, ""]
    return "\n".join(lines)


def score() -> None:
    questions = load_jsonl(QUESTIONS_PATH)
    by_id = {q["id"]: q for q in questions}
    latest = {pair: r for pair, r in latest_records(load_jsonl(RAW_PATH)).items() if pair[0] in by_id}
    if not latest:
        sys.exit(f"No results in {RAW_PATH} yet. Run: python -m eval.answer_eval run")
    absent = [(q["id"], m) for q in questions for m in MODES if (q["id"], m) not in latest]
    if absent:
        print(f"WARNING: {len(absent)} (question, mode) pairs have no result yet, e.g. {absent[:3]}. "
              "The tables only cover what was run.")
    failed = [pair for pair, r in latest.items() if "error" in r]
    if failed:
        print(f"WARNING: {len(failed)} answers are errors, e.g. {failed[:3]}. "
              "Run `python -m eval.answer_eval run` again to retry them before you report the numbers.")

    scored = [score_one(by_id[qid], record) for (qid, _), record in latest.items()]
    by_mode = {m: [r for r in scored if r["mode"] == m] for m in MODES}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with SCORES_PATH.open("w", encoding="utf-8") as f:
        for row in scored:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    TABLE_PATH.write_text(results_markdown(questions, by_mode, list(latest.values())), encoding="utf-8")
    GRADING_PATH.write_text(grading_markdown(questions, latest), encoding="utf-8")

    print("\n".join(overall_table(by_mode)))
    print(f"\nSaved {TABLE_PATH}, {SCORES_PATH} and {GRADING_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer evaluation: run the questions, then score them.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="ask the questions (LLM calls), saving each result as it arrives")
    run_parser.add_argument("env_file", nargs="?", help="default .env (local); .env.neon for Neon")
    run_parser.add_argument("--limit", type=int, help="only the first N questions (smoke test)")
    run_parser.add_argument("--mode", choices=MODES, help="only this mode (default: both)")
    run_parser.add_argument("--pause", type=float, default=PAUSE_SECONDS, help="seconds to wait between questions")
    sub.add_parser("score", help="compute the metrics from the saved results (no LLM calls)")
    args = parser.parse_args()

    if args.command == "score":
        score()
        return
    # config.py reads ENV_FILE at import time; app is only imported inside run(), after this.
    if args.env_file:
        if not Path(args.env_file).is_file():
            sys.exit(f"Env file not found: {args.env_file}")
        os.environ["ENV_FILE"] = args.env_file
    run(args.limit, [args.mode] if args.mode else list(MODES), args.pause)


if __name__ == "__main__":
    main()
