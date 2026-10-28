# app/main.py
"""HTTP routes. They stay thin: SQL lives in ingest.py, prompts in answer.py and agent.py.

Every route that touches the database, the embedding model or the LLM is a plain `def`,
so FastAPI runs it in a worker thread instead of blocking the event loop.
"""
import logging
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, StringConstraints

from app import agent, answer, config, db, ingest
from app.llm import LLMUnavailable

log = logging.getLogger(__name__)
app = FastAPI(title="AI Investigation Engine")

INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"  # independent of the working directory


@app.exception_handler(LLMUnavailable)
async def llm_unavailable(request: Request, error: LLMUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(error)})  # the message is safe to show


@app.exception_handler(psycopg.OperationalError)
async def database_unreachable(request: Request, error: psycopg.OperationalError):
    log.warning("Database error on %s: %s", request.url.path, error)  # full reason in the logs only
    return JSONResponse(status_code=503, content={"detail": "database unreachable"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(INDEX_HTML)


@app.get("/health")
def health():
    # Never touches the database: Render pings this, and Neon compute hours are limited.
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    try:
        db.ping()
    except psycopg.OperationalError as e:
        log.warning("Database check failed: %s", e)  # full reason in the logs only
        return JSONResponse(status_code=503, content={"status": "error", "detail": "database unreachable"})
    return {"status": "ok"}


# ---------- Documents ----------

@app.post("/api/documents")
def upload_document(file: UploadFile):
    """Add, update (same file name, new content) or skip (same content) one uploaded file."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() not in ingest.SUPPORTED_FORMATS:
        raise HTTPException(415, "Unsupported file type: upload a PDF, DOCX, TXT or MD file.")
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)  # one byte more than allowed is enough to know
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        doc = ingest.load_document(filename, data)
    except ingest.IngestError as e:
        raise HTTPException(422, str(e)) from None

    with db.get_conn() as conn:
        if ingest.is_protected_name(conn, ingest.UPLOAD_SOURCE, doc.metadata["file_name"]):
            raise HTTPException(403, "A protected document has this file name; it cannot be replaced.")
        status, document_id, n_chunks = ingest.ingest(conn, doc, ingest.UPLOAD_SOURCE)
        stored = ingest.get_document(conn, document_id)  # for a duplicate: the document already stored
    return {"status": status, "document_id": document_id, "title": stored["title"],
            "version": stored["version"], "chunks": n_chunks}


@app.get("/api/documents")
def list_documents(source: str | None = None,
                   limit: Annotated[int, Query(ge=1, le=200)] = 50,
                   offset: Annotated[int, Query(ge=0)] = 0):
    """Documents newest first. Without ?source= the HotpotQA corpus is left out."""
    with db.get_conn() as conn:
        total, documents = ingest.list_documents(conn, source, limit, offset)
    return {"total": total, "documents": documents}


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: UUID):
    with db.get_conn() as conn:
        document = ingest.get_document(conn, document_id)
        if document is None:
            raise HTTPException(404, "Document not found.")
        if document["is_protected"]:
            raise HTTPException(403, "This document is protected and cannot be deleted.")
        ingest.delete_document(conn, document_id)
    return {"deleted": document_id}


# ---------- Questions ----------

class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    mode: Literal["simple", "agent"] = "simple"


@app.post("/api/ask")
def ask(request: AskRequest):
    """Answer JSON as answer.py builds it: status, answer, citations, conflicts, missing."""
    with db.get_conn() as conn:
        if request.mode == "agent":
            result, _trace = agent.run_agent(conn, request.question)  # the trace is for the eval only
            return result
        return answer.answer_question(conn, request.question)
