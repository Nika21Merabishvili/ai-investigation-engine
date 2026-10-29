# AI Investigation Engine

I built a question-answering system over a large document collection. You ask a question in plain English. It searches more than 50,000 documents with hybrid search (vectors plus keywords), sends the best passages to Gemini, and returns a short answer where every sentence cites its source. If two sources disagree, the answer lists the conflict. If the sources don't contain the answer, it returns `insufficient` instead of guessing. There are two answer modes: simple (one search, one LLM call) and agent (the model runs its own searches, up to 3 rounds).

The documents are Wikipedia paragraphs from the HotpotQA dataset plus 20 made-up documents about a payments company, NovaPay. <!-- EDIT: one sentence on the context (Upgaming Talent Growth Program, Day 4) and what you wanted to learn -->

## Live demo

https://ai-investigation-engine.onrender.com/

It runs on Render's free tier. The instance sleeps after 15 idle minutes, so the first request after a pause can be slow. TODO(Nika): how long a cold start usually takes (not recorded in the repo).

## Architecture

Everything lives in one Postgres database with two tables, `documents` and `chunks`. Each chunk has its text, a 384-number embedding stored as `halfvec(384)` with an HNSW index (cosine), and a generated `tsvector` column with a GIN index for keyword search. A question runs both searches, and my own `rrf()` merges the two rankings. Simple mode sends the top 8 chunks to Gemini once. Agent mode gives Gemini a `search_documents` tool and lets it search for up to 3 rounds. Both modes end in the same check, `finalize()`, which drops citations to sources the model never saw and withholds an answer that cites nothing valid.

```
Ingest
  upload (POST /api/documents) or scripts/ingest_bulk.py company
    -> load_document()     PDF (pypdf), DOCX (python-docx), TXT / MD
    -> content_hash()      SHA-256 of the normalized text -> added / updated / duplicate
    -> paragraph_chunks()  blocks of up to 200 words, each chunk starts "Title: ..."
    -> embed_passages()    fastembed, BAAI/bge-small-en-v1.5, 384 numbers
    -> Postgres            documents + chunks (halfvec(384), tsvector)

  HotpotQA: scripts/build_hotpot.py -> data/hotpot_paragraphs.jsonl
    -> scripts/ingest_bulk.py hotpot   one chunk per paragraph, embeddings cached in data/embeddings.npz

Question (POST /api/ask)
  -> hybrid_search()   dense top 40 (HNSW, cosine) + keyword top 40 (tsvector, GIN) -> rrf(k=60)
  -> simple mode       top 8 chunks -> similarity gate -> one Gemini call
     agent mode        search_documents tool, 5 chunks per search, up to 3 rounds
  -> finalize()        checks the [S#] citations against the chunks the model saw
  -> JSON              status, answer, citations, conflicts, missing
```

| File | What it does |
| --- | --- |
| `app/main.py` | HTTP routes. Turns Gemini and database failures into 503 errors. |
| `app/ingest.py` | Loaders, SHA-256 dedup, add / update / duplicate logic, both chunkers, `ingest()`, document queries. |
| `app/embed.py` | fastembed wrapper. Adds the BGE query prefix to questions. |
| `app/search.py` | Dense SQL, keyword SQL, `rrf()`, `hybrid_search()`. |
| `app/answer.py` | Simple mode: prompt, JSON parsing with one retry, similarity gate, `finalize()`. |
| `app/agent.py` | Agent mode: the tool loop, max 3 rounds, fallback to a simple-mode prompt. |
| `app/llm.py` | Gemini through the `openai` SDK. 30 s timeout and the retry policy. |
| `app/config.py`, `app/db.py` | Settings from the environment. Database connection. |
| `static/index.html` | The one-page UI: ask in simple or agent mode, see answer, conflicts, missing facts and sources, upload / list / delete documents. |
| `schema.sql`, `indexes.sql` | The two tables. The HNSW and GIN indexes, created after a bulk load. |
| `scripts/` | `init_db`, `build_hotpot`, `build_company_docs`, `ingest_bulk`, `create_indexes`, `download_model`, plus dev tools (`ask`, `show_sources`, `try_search`, `eyeball_threshold`, `llm_smoke`, `check_chunks`). |
| `eval/` | Retrieval, chunking and answer evaluations, metrics, question sets, saved results. |
| `test/` | pytest tests. Gemini is replaced by fakes. |

## How to run it locally

You need Python 3.12 and Docker.

**1. Python environment**

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements-dev.txt
```

`requirements-dev.txt` adds `datasets`, `fpdf2` and `pytest` to the app's `requirements.txt`. The build scripts and the tests need them.

**2. Settings.** Copy `.env.example` to `.env` and fill it in:

- `DATABASE_URL`: the local Docker database. `docker-compose.yml` publishes Postgres on host port 5433, but `.env.example` uses 5432, so change the port.
- `GEMINI_API_KEY` and `GEMINI_MODEL`.
- Optional, not in `.env.example`: `MIN_DENSE_SIMILARITY`. If the best chunk's cosine similarity is below it, simple mode returns `insufficient` without calling Gemini. The default 0.0 turns this gate off. TODO(Nika): the value you use locally and on Render (the error analysis mentions 0.62).

**3. Database**

```
docker compose up -d
python -m scripts.init_db
```

**4. Data.** `data/company/` is in git. The HotpotQA file is not, so build it first.

```
python -m scripts.build_hotpot                     # downloads HotpotQA, writes data/hotpot_paragraphs.jsonl
python -m scripts.build_company_docs               # only if you changed data/company_src/
python -m scripts.ingest_bulk company
python -m scripts.ingest_bulk hotpot --limit 1000  # optional quick check
python -m scripts.ingest_bulk hotpot
python -m scripts.create_indexes                   # HNSW + GIN, after the load
```

`ingest_bulk` is safe to stop and rerun. It skips documents that are already loaded and keeps every embedding in `data/embeddings.npz`.

**5. Run the app**

```
uvicorn app.main:app
```

Then open http://127.0.0.1:8000/. FastAPI's generated API docs are at `/docs`.

**6. Tests**

```
pytest -q
```

On 2026-10-29 this gave 130 passed and 1 skipped. The skipped test is in `test/test_ingest.py`. It needs the local Postgres running and rolls back everything it writes.

**7. Neon (the live database).** `.env.neon` has the same variables as `.env`, with Neon's `DATABASE_URL`.

```
python -m scripts.init_db .env.neon
python -m scripts.ingest_bulk all .env.neon
python -m scripts.create_indexes .env.neon
```

The embeddings come from the cache, so nothing is embedded twice. To run the app itself against Neon, set `ENV_FILE=.env.neon` before `uvicorn` (`app/config.py` reads it).

**8. Docker**

```
docker build -t ai-investigation-engine .
docker run --env-file .env.neon -p 8000:8000 ai-investigation-engine
```

The build bakes the embedding model into the image (`scripts/download_model.py`), so the container never downloads it at start. `.dockerignore` keeps `.env*`, `data/` and `models/` out of the image. Inside the container, `localhost` is the container itself, so pass an env file with a database the container can reach. Render builds the same Dockerfile and sets `PORT`.

## API

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/` | The UI (`static/index.html`). |
| GET | `/health` | `{"status": "ok"}`. Never touches the database. |
| GET | `/health/db` | Runs `SELECT 1`. 503 if the database is unreachable. |
| POST | `/api/documents` | Upload one file (multipart field `file`): PDF, DOCX, TXT or MD, max 5 MB. Returns `status` (`added`, `updated` or `duplicate`), `document_id`, `title`, `version`, `chunks`. 415 wrong type, 413 too big, 422 unreadable, 403 if a protected document has that file name. |
| GET | `/api/documents` | Documents, newest first, with `total`. Query: `source`, `limit` (1-200, default 50), `offset`. HotpotQA rows are left out unless you ask for `?source=hotpotqa`. |
| DELETE | `/api/documents/{id}` | Deletes a document and its chunks. 404 unknown id, 403 protected (the seed corpus). |
| POST | `/api/ask` | Body `{"question": "...", "mode": "simple"}` or `"agent"`. Question 1-1000 characters, mode defaults to `simple`. Returns the answer JSON. 503 if Gemini or the database is unavailable. |

Example request:

```
curl -X POST https://ai-investigation-engine.onrender.com/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many card payments were charged twice during the 18 March incident?", "mode": "simple"}'
```

Example response. This is the saved simple-mode answer to eval question `co_conflict_01` from `eval/results/answers_raw.jsonl` (local database, so chunk ids differ on Neon). I shortened the chunk texts.

```json
{
  "status": "partial",
  "answer": "Sources disagree on the exact number of card payments charged twice, stating either 1,284 card payments [S1][S2] or 1,317 duplicate charges [S7].",
  "citations": [
    {"id": "S1", "document_title": "Incident Report INC-2026-031", "chunk_id": 18, "text": "Title: Incident Report INC-2026-031\n..."},
    {"id": "S2", "document_title": "Postmortem INC-2026-031: Duplicate Card Charges", "chunk_id": 30, "text": "Title: Postmortem INC-2026-031: Duplicate Card Charges\n..."},
    {"id": "S7", "document_title": "Memo: Refunds for INC-2026-031", "chunk_id": 16, "text": "Title: Memo: Refunds for INC-2026-031\n..."}
  ],
  "conflicts": [
    {
      "topic": "number of duplicate card payments and total amount",
      "positions": [
        {"claim": "1,284 card payments were charged twice, totaling EUR 186,420", "sources": ["S1", "S2"]},
        {"claim": "1,317 duplicate charges were refunded, totaling EUR 191,236.50", "sources": ["S7"]}
      ]
    }
  ],
  "missing": []
}
```

`status` is `answered`, `partial` or `insufficient`. An `insufficient` answer always has an empty `answer`, no citations, no conflicts, and says what is missing in `missing`.

## Stack choices and why

- **Python 3.12 + FastAPI.** Routes that touch the database, the model or the LLM are plain `def`, so FastAPI runs them in a worker thread. <!-- EDIT: why FastAPI for you -->
- **psycopg 3 with plain SQL, no ORM.** The search queries use pgvector operators and full-text functions directly. <!-- EDIT: why you chose plain SQL -->
- **Postgres + pgvector.** Documents, vectors and keyword search sit in one database, so there is no second service to host. <!-- EDIT: anything else that decided it -->
- **`halfvec(384)`.** 16-bit floats take half the space of `vector(384)`. <!-- EDIT: confirm this was about Neon's 0.5 GB limit -->
- **HNSW, cosine.** HNSW returns at most `ef_search` rows (default 40), so hybrid search asks each retriever for 40 candidates. <!-- EDIT: why HNSW over IVFFlat -->
- **`tsvector` + GIN.** The `tsv` column is generated in `schema.sql`, so Postgres keeps it in sync with the text. <!-- EDIT: why keyword search at all (names, IDs like CHG-0419?) -->
- **My own weighted RRF, k = 60.** It combines ranks, not scores, so cosine similarity and `ts_rank` don't need to be on the same scale. Both weights are 1.0 right now. <!-- EDIT: why you wrote it yourself -->
- **fastembed + BAAI/bge-small-en-v1.5.** Runs as ONNX on the CPU, with no PyTorch in `requirements.txt`. 384 dimensions. <!-- EDIT: why this model -->
- **Gemini through the `openai` SDK.** Gemini has an OpenAI-compatible endpoint, so the code uses the standard chat and tool-calling calls. The eval ran on `gemini-3.5-flash-lite`. <!-- EDIT: why Gemini (free tier? tool calling?) -->
- **One static `index.html`.** No build step. FastAPI serves it at `/`. All model output goes in through `textContent`, never `innerHTML`. <!-- EDIT -->
- **Docker.** The same image runs locally and on Render.
- **Neon + Render free tiers.** <!-- EDIT: why these two hosts -->

## Data

- **HotpotQA** (distractor setting, validation split). `scripts/build_hotpot.py` takes every context paragraph and drops repeats by SHA-256 of the normalized text. Result: 66,555 unique paragraphs in `data/hotpot_paragraphs.jsonl`, all from validation. (The script tops up from the train split only if validation gives fewer than 50,000; it didn't need to.) Each paragraph is loaded as one document with one chunk.
- **NovaPay.** 20 synthetic documents about one incident (duplicate card charges on 18 March 2026) in `data/company/`: 6 Markdown, 4 TXT, 5 PDF, 5 DOCX. `scripts/build_company_docs.py` builds them from `data/company_src/`. They contain 3 planted contradictions and 2 facts that appear in no document. The answer key is `eval/company_scenario.md`, which is never ingested.
- The seed corpus is stored with `is_protected = true`, so the API refuses to delete it.
- **Counts in the database:** TODO(Nika): paste the per-source table that `python -m scripts.ingest_bulk` prints at the end (documents and chunks), for local and for Neon. It isn't saved in the repo.
- **Reproducing:** seed 42 picks the 200 retrieval questions (`build_hotpot.py`) and the 25 HotpotQA answer questions (`build_eval_questions.py`). The paragraph corpus isn't sampled (it takes every validation paragraph), so it needs no seed. Commands are in step 4 above.

## Evaluation summary

- **Retrieval, 200 HotpotQA questions:** Recall@5 is 0.728 for dense only and 0.720 for hybrid. Hybrid is better only at Recall@10 (0.818 vs 0.787) and is much slower (346 ms vs 23 ms per query).
- **HotpotQA answers (25 questions):** the gold answer appears in the answer for 0.560 of simple-mode answers and 0.880 of agent-mode answers.
- **Citation accuracy:** 0.964 simple, 0.962 agent.
- **Abstention:** both modes abstained on 3 of 5 unanswerable questions. Simple mode wrongly abstained on 8 of 40 answerable ones, agent mode on 1.
- **Contradictions:** a conflict was reported on 4 of 5 contradiction questions in simple mode and 3 of 5 in agent mode.

Full tables, error analysis and limits: [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md).

## Free-tier limits

**Render** (about 512 MB RAM, 0.1 CPU, sleeps after 15 idle minutes)

- The embedding model is baked into the Docker image, so a cold start doesn't download it. It loads on the first search and stays in memory.
- Uploads are capped at 5 MB.
- TODO(Nika): memory use on Render, if you checked it in the dashboard. No measurement is saved in the repo.

**Neon** (0.5 GB storage, 100 compute-hours a month)

- `/health` never touches the database, because Render pings it and Neon compute hours are limited. `/health/db` is the separate database check.
- Embeddings are `halfvec` (16-bit floats). Only paragraph chunks are stored. The chunking experiment refuses to run against Neon.
- Indexes are built once, after the bulk load.
- Connections time out after 10 s. A database error returns 503 `database unreachable`, and the full reason goes only to the logs.
- TODO(Nika): Neon database size. It isn't recorded anywhere in the repo. One way to get it: `SELECT pg_size_pretty(pg_database_size(current_database()));`

**Gemini** (TODO(Nika): the free-tier limits for your model, requests per minute and per day)

- Each call has a 30 s timeout. A timeout is not retried.
- 429, 5xx and connection errors are retried after 2, 4 and 8 seconds. Then the API returns 503 with "The AI service is busy right now. Please try again in a minute."
- Simple mode skips the LLM call when the similarity gate finds no close document.
- Agent mode makes at most 5 calls: 3 rounds, plus a fallback that can retry once.
- The answer eval pauses 4 s between questions, stops after 3 failures in a row, saves each answer as it arrives, and picks up where it stopped. Scoring reads the saved file and needs no LLM.

## Known limitations

- **No auth on upload or delete.** Anyone with the URL can upload files or delete uploaded ones; only the seed corpus is protected. Next: an API key or a login for write routes.
- **Four file extensions only.** PDF, DOCX, TXT and MD, and no OCR, so a scanned PDF is rejected as "no text found". <!-- EDIT: what you'd add next -->
- **One LLM provider, no fallback.** All calls go to Gemini; if it is down or out of quota, the API returns 503. Next: a second provider (for example Groq) behind the same functions in `app/llm.py`.
- **Contradiction detection is prompt-only.** One prompt rule asks the model to list conflicts; the code only checks that each side cites a real source. It missed 1 of 5 in simple mode and 2 of 5 in agent mode. <!-- EDIT: what you'd do next -->
- **The similarity gate is rough.** It looks only at dense similarity, and I picked the threshold by eye with `scripts/eyeball_threshold.py` (10 questions). In the eval it blocked 4 simple-mode questions; in 3 of them a gold page was in the top 8. Next: gate on the fused hybrid score.
- **An update replaces the old version.** Re-uploading a file with the same name and new content bumps `version` and deletes the old chunks; no history is kept.
- **Small synthetic company corpus.** 20 NovaPay documents about one incident.
- **Small eval set, one grader.** 45 questions, 5 per NovaPay question type. Claude drafted the NovaPay grades. TODO(Nika): say whether you reviewed them.
- **No CI.** There is no workflow file; I run `pytest` by hand. Next: a GitHub Actions job that runs `pytest -q`.
- **Render cold starts.** The first request after 15 idle minutes waits for the instance to wake up.

## More documents

- [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md): setup, metrics, results, error analysis.
- [docs/AI_USAGE_REPORT.md](docs/AI_USAGE_REPORT.md): how I used AI tools on this project.
