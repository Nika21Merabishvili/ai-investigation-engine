# scripts/build_eval_questions.py
"""Build eval/questions.jsonl: 25 HotpotQA questions sampled from the dataset + your NovaPay questions.

Reads:   HotpotQA distractor validation (from your Hugging Face cache; Day 1 downloaded it)
         eval/company_questions.jsonl (hand-written, one question per line)
Checks:  every gold document exists in the database, so a typo can't silently score 0
Writes:  eval/questions.jsonl

Company questions name their gold documents by FILE NAME without extension
("postmortem_INC-2026-031"), because you know those for sure. This script finds the company
document whose external_id (its file name) has that name and stores its title, because the
search results carry titles and every metric compares titles.

Run from the repo root (no LLM calls):
    python -m scripts.build_eval_questions              # database from .env
    python -m scripts.build_eval_questions .env.neon    # database from .env.neon
"""
import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

DATASET, CONFIG = "hotpotqa/hotpot_qa", "distractor"   # same as scripts/build_hotpot.py
SEED = 42
N_BRIDGE = 15       # the plan: 25 HotpotQA questions, 15 bridge + 10 comparison
N_COMPARISON = 10

COMPANY_SOURCE = "company"                 # documents.source of the NovaPay files (scripts/ingest_bulk.py)
KNOWN_SOURCES = {"hotpotqa", COMPANY_SOURCE}
COMPANY_PATH = Path("eval/company_questions.jsonl")
OUT_PATH = Path("eval/questions.jsonl")

TYPE_ORDER = ["bridge", "comparison", "simple", "multi_doc", "contradiction", "unanswerable"]
EXPECTED = {"simple": "answer", "multi_doc": "answer", "contradiction": "flag_conflict", "unanswerable": "insufficient"}
REQUIRED_KEYS = {"id", "type", "question", "gold_answer", "gold_files", "expected"}


# ---------------------------------------------------------------- pure helpers (tested)

def check_company_question(q: dict) -> list[str]:
    """Everything wrong with one hand-written question. An empty list means it's fine."""
    missing = REQUIRED_KEYS - q.keys()
    if missing:
        return [f"missing keys {sorted(missing)}"]
    if q["type"] not in EXPECTED:
        return [f"type must be one of {sorted(EXPECTED)}"]
    problems = []
    if q["expected"] != EXPECTED[q["type"]]:
        problems.append(f"a {q['type']} question must have expected {EXPECTED[q['type']]!r}")
    n_gold = len(q["gold_files"])
    if q["type"] == "unanswerable" and n_gold:
        problems.append("an unanswerable question has no gold files")
    if q["type"] in ("multi_doc", "contradiction") and n_gold < 2:
        problems.append(f"a {q['type']} question needs at least 2 gold files")
    if q["type"] == "simple" and n_gold < 1:
        problems.append("a simple question needs a gold file")
    if "check" in q:
        problems.append(f"still has a 'check' note ({q['check']}). Confirm it in the document, then delete the note")
    return problems


def file_stem(external_id: str) -> str:
    """'postmortem_INC-2026-031.docx' -> 'postmortem_INC-2026-031' (also if a folder is in front)."""
    return Path(external_id.replace("\\", "/")).stem


def title_for_file(company_docs: list[tuple[str, str]], stem: str) -> str:
    """The title of the one company document (title, external_id) whose file name is `stem`."""
    titles = sorted({title for title, external_id in company_docs if file_stem(external_id) == stem})
    if len(titles) == 1:
        return titles[0]
    if titles:
        sys.exit(f"File name {stem!r} matches several documents with different titles: {titles}")
    listing = "\n".join(f"  {file_stem(external_id):40} -> {title}" for title, external_id in company_docs)
    sys.exit(f"No company document has the file name {stem!r}. The company documents in this database:\n{listing}")


# ---------------------------------------------------------------- reading the inputs

def sample_hotpot() -> list[dict]:
    """The first N_BRIDGE bridge and N_COMPARISON comparison questions of a seeded shuffle."""
    from datasets import load_dataset

    rows = load_dataset(DATASET, CONFIG, split="validation")
    order = list(range(len(rows)))
    random.Random(SEED).shuffle(order)

    wanted = {"bridge": N_BRIDGE, "comparison": N_COMPARISON}
    taken = Counter()
    picked = []
    for i in order:
        row = rows[i]
        kind = row["type"]
        if taken[kind] >= wanted.get(kind, 0):
            continue
        taken[kind] += 1
        picked.append({
            "id": f"hp_{kind}_{taken[kind]:02d}",
            "source": "hotpotqa",
            "type": kind,
            "expected": "answer",
            "question": row["question"],
            "gold_answer": row["answer"],
            "gold_titles": list(dict.fromkeys(row["supporting_facts"]["title"])),  # unique, in order
            "hotpot_id": row["id"],
        })
        if taken == Counter(wanted):
            break
    return picked


def load_company() -> list[dict]:
    questions = []
    lines = COMPANY_PATH.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            q = json.loads(line)
        except json.JSONDecodeError as error:
            sys.exit(f"{COMPANY_PATH}:{line_no}: not valid JSON ({error.msg}, column {error.colno}). Check quotes and commas.")
        problems = check_company_question(q)
        if problems:
            sys.exit(f"{COMPANY_PATH}:{line_no} ({q.get('id', '?')}): " + "; ".join(problems))
        questions.append(q)
    return questions


# ---------------------------------------------------------------- database checks

def print_sources(cur) -> None:
    """Show what the database holds, and warn about documents that would change the scores."""
    cur.execute("SELECT source, count(*) FROM documents GROUP BY source ORDER BY count(*) DESC")
    counts = dict(cur.fetchall())
    print("Database: " + " · ".join(f"{source} {n:,}" for source, n in counts.items()))
    extra = {source: n for source, n in counts.items() if source not in KNOWN_SOURCES}
    if extra:
        cur.execute("SELECT source, title FROM documents WHERE NOT (source = ANY(%s)) ORDER BY source, title LIMIT 10",
                    (sorted(KNOWN_SOURCES),))
        examples = "\n".join(f"  [{source}] {title}" for source, title in cur.fetchall())
        print(f"WARNING: {sum(extra.values())} documents are neither HotpotQA nor company documents (uploads from testing?).\n"
              f"They can appear in search results and change the scores. Delete them in the app before evaluating:\n{examples}")


def company_documents(cur) -> list[tuple[str, str]]:
    cur.execute("SELECT title, external_id FROM documents WHERE source = %s ORDER BY external_id", (COMPANY_SOURCE,))
    docs = cur.fetchall()
    if not docs:
        sys.exit(f"No documents with source = {COMPANY_SOURCE!r} in this database. "
                 "Check COMPANY_SOURCE against scripts/ingest_bulk.py, and that .env points at the loaded database.")
    return docs


def add_company_titles(company_docs: list[tuple[str, str]], questions: list[dict]) -> list[dict]:
    """Company questions in the output shape, with file names turned into titles."""
    out = []
    for q in questions:
        out.append({
            "id": q["id"],
            "source": "company",
            "type": q["type"],
            "expected": q["expected"],
            "question": q["question"],
            "gold_answer": q["gold_answer"],
            "gold_titles": [title_for_file(company_docs, stem) for stem in q["gold_files"]],
            # Documents that also state the fact: citing one counts as correct, but recall doesn't require them.
            "acceptable_titles": [title_for_file(company_docs, stem) for stem in q.get("acceptable_files", [])],
            "gold_files": q["gold_files"],
        })
    return out


def check_titles_exist(cur, questions: list[dict]) -> None:
    wanted = sorted({title for q in questions for title in q["gold_titles"]})
    cur.execute("SELECT DISTINCT title FROM documents WHERE title = ANY(%s)", (wanted,))
    found = {row[0] for row in cur.fetchall()}
    missing = [title for title in wanted if title not in found]
    if missing:
        sys.exit(f"{len(missing)} gold titles are not in the database, e.g. {missing[:5]}. Is the env file pointing at the loaded database?")


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="Build eval/questions.jsonl.")
    parser.add_argument("env_file", nargs="?", help="default .env (local); .env.neon for Neon")
    args = parser.parse_args()
    # config.py reads ENV_FILE at import time, so it must be set before importing app.
    if args.env_file:
        if not Path(args.env_file).is_file():
            sys.exit(f"Env file not found: {args.env_file}")
        os.environ["ENV_FILE"] = args.env_file
    from psycopg.rows import tuple_row

    from app import db

    company_raw = load_company()       # fail fast on a broken line, before downloading anything
    hotpot = sample_hotpot()

    with db.get_conn() as conn, conn.cursor(row_factory=tuple_row) as cur:
        print_sources(cur)
        company = add_company_titles(company_documents(cur), company_raw)
        questions = hotpot + company
        check_titles_exist(cur, questions)

    repeated = [qid for qid, n in Counter(q["id"] for q in questions).items() if n > 1]
    if repeated:
        sys.exit(f"Question ids must be unique; repeated: {repeated}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    by_type = Counter(q["type"] for q in questions)
    by_expected = Counter(q["expected"] for q in questions)
    print(f"Wrote {OUT_PATH}: {len(questions)} questions")
    print("  " + " · ".join(f"{t} {by_type[t]}" for t in TYPE_ORDER))
    print("  expected: " + " · ".join(f"{e} {n}" for e, n in sorted(by_expected.items())))
    absent = [t for t in TYPE_ORDER if by_type[t] == 0]
    if len(questions) < 40 or absent:
        print(f"WARNING: the brief needs 40+ questions covering every type; missing types: {absent or 'none'}")


if __name__ == "__main__":
    main()
