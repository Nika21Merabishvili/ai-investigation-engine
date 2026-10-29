# AI usage report

This report is built from my AI usage log, [docs/AI_USAGE_LOG.md](AI_USAGE_LOG.md), with dates checked against `git log`.

## 1. Summary

I used two AI tools: Claude (chat) and Claude Code. The log has 6 entries: 4 for Claude and 2 for Claude Code. One entry is from 2026-10-26 (Day 1) and five are from 2026-10-29 (Day 4).

This draft of the README and the two reports was written by Claude Code on 2026-10-29. It is not in the log yet. TODO(Nika): add a line for it to `docs/AI_USAGE_LOG.md`.

`git log` shows commits on 26, 27, 28 and 29 October. The log has no entries for 27 and 28 October, when I built the loaders, chunkers, search, RRF, the retrieval and chunking evaluations, cited answers, agent mode, the API and the UI. TODO(Nika): add log entries for those days, or say here that you used no AI on them.

## 2. How I used AI

| Area | Tool | What AI did | What I kept or changed |
| --- | --- | --- | --- |
| Boilerplate code | Claude | Day 1 local setup: requirements files, `.gitignore`, venv. | Kept. |
| Boilerplate code (eval) | Claude | Day 4 question set: the builder script (`scripts/build_eval_questions.py`), 20 drafted NovaPay questions, and tests. | Kept. |
| Boilerplate code (eval) | Claude | `eval/answer_eval.py` (resumable run, offline score), plus metric stubs and tests. | Kept. I wrote the metrics myself. |
| Evaluation run | Claude Code | Verified the Day 4 files and the facts in the questions, then ran and scored the 90-answer evaluation. | Kept. |
| Grading | Claude | Drafted hand grades for the 40 NovaPay answers, with the grading rule and a reason for each grade (`eval/results/company_answers_for_grading.md`). | Kept. TODO(Nika): the file's "reviewed by" line is still empty. |
| Docs | Claude Code | Drafted the error analysis (10 failures, 4 groups) in `eval/results/error_analysis.md`. | Kept. |
| Docs | Claude Code | Drafted `README.md`, `docs/EVALUATION_REPORT.md` and this file. | TODO(Nika): what you changed. |
| SQL | – | No log entry. | TODO(Nika) |
| UI | – | No log entry. | TODO(Nika) |
| Docker | – | No log entry. | TODO(Nika) |
| Debugging | – | No log entry. | TODO(Nika) |

## 3. What I wrote myself

| Part | Where | AI's role, as the log states it |
| --- | --- | --- |
| The two chunkers | `paragraph_chunks()` and `fixed_chunks()` in `app/ingest.py` | TODO(Nika): no log entry. |
| `rrf()` | `app/search.py` | TODO(Nika): no log entry. |
| The metrics | `eval/metrics.py` | For the Day 4 answer metrics, Claude wrote the stubs and tests, and I wrote the metrics. TODO(Nika): no log entry for `recall_at_k()` and `mrr()` (committed on 27 October). |
| The agent loop | `run_agent()` in `app/agent.py` | TODO(Nika): no log entry. |

<!-- EDIT: one or two sentences per part on what was hard and what you learned writing it -->

## 4. Where AI was wrong or I changed its output

Every entry in the log ends with "kept". The log records no case where I rejected or changed AI output.

<!-- EDIT: add concrete cases you remember: a bug in AI code you had to fix, a suggestion you turned down, a fact in the drafted questions or grades that was wrong. If there were none, say so plainly. -->

## 5. How I checked AI-written code

What the log supports:

- The question builder and the metric stubs both came with tests written by Claude (log entries 2 and 3). TODO(Nika): confirm the answer metrics you wrote were checked against those tests.
- Claude Code checked the Day 4 files and the facts in the drafted questions before running the evaluation. That is AI checking AI, not a check by me.

<!-- EDIT: how you checked things yourself, for example reading the code line by line, running the tests, trying the app by hand, comparing answers with eval/company_scenario.md, checking grades against the raw answers. -->

## 6. Reflection

<!-- EDIT: Where did AI save you the most time, and where did it cost you time (wrong code, extra checking)? -->

<!-- EDIT: Which part of the project do you understand least because AI wrote it, and what would you do about that? -->

<!-- EDIT: Claude drafted the hand grades and the error analysis. Was that OK for an evaluation, and what would you do differently next time (log every session, grade first and compare with AI after, write more parts yourself)? -->

## Raw log

[docs/AI_USAGE_LOG.md](AI_USAGE_LOG.md)
