# tests/test_api.py
"""The API routes through TestClient. The database, ingest, answer and agent functions are faked."""
from contextlib import nullcontext
from datetime import datetime, timezone
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import agent, answer, config, db, ingest, main
from app.llm import FRIENDLY_MESSAGE, LLMUnavailable

client = TestClient(main.app)

DOC_ID = UUID("6f1c2d3e-4a5b-4c6d-8e9f-0a1b2c3d4e5f")
ANSWER = {
    "status": "answered",
    "answer": "Payments failed after the config change [S1].",
    "citations": [{"id": "S1", "document_title": "Incident", "chunk_id": 7, "text": "Title: Incident\n..."}],
    "conflicts": [],
    "missing": [],
}


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    """Routes get conn=None; the faked functions below never use it."""
    monkeypatch.setattr(db, "get_conn", lambda: nullcontext())


def not_called(*args, **kwargs):
    raise AssertionError("this function must not be called")


def document(**fields):
    base = {"id": DOC_ID, "title": "Runbook", "source": "upload", "file_format": "md", "version": 1,
            "is_protected": False, "updated_at": datetime(2026, 10, 1, tzinfo=timezone.utc)}
    return {**base, **fields}


def upload(filename, data):
    return client.post("/api/documents", files={"file": (filename, data, "application/octet-stream")})


# --- POST /api/documents ------------------------------------------------------

def test_oversized_upload_is_413(monkeypatch):
    monkeypatch.setattr(ingest, "load_document", not_called)
    monkeypatch.setattr(ingest, "ingest", not_called)
    response = upload("big.txt", b"a" * (config.MAX_UPLOAD_BYTES + 1))
    assert response.status_code == 413


def test_wrong_extension_is_415(monkeypatch):
    monkeypatch.setattr(ingest, "ingest", not_called)
    response = upload("photo.png", b"\x89PNG")
    assert response.status_code == 415


def test_file_without_text_is_422(monkeypatch):
    monkeypatch.setattr(ingest, "ingest", not_called)
    response = upload("empty.txt", b"  \n\n  ")
    assert response.status_code == 422
    assert "no text found" in response.json()["detail"]


def test_upload_over_a_protected_name_is_403(monkeypatch):
    monkeypatch.setattr(ingest, "is_protected_name", lambda conn, source, file_name: True)
    monkeypatch.setattr(ingest, "ingest", not_called)
    response = upload("runbook.md", b"# Runbook\n\nRestart the payment service.")
    assert response.status_code == 403


def test_upload_returns_status_and_document(monkeypatch):
    calls = []

    def fake_ingest(conn, doc, source):
        calls.append((doc.metadata["file_name"], source))
        return "updated", DOC_ID, 3

    monkeypatch.setattr(ingest, "is_protected_name", lambda conn, source, file_name: False)
    monkeypatch.setattr(ingest, "ingest", fake_ingest)
    monkeypatch.setattr(ingest, "get_document", lambda conn, document_id: document(version=2))

    response = upload("runbook.md", b"# Runbook\n\nRestart the payment service.")

    assert response.status_code == 200
    assert response.json() == {"status": "updated", "document_id": str(DOC_ID), "title": "Runbook",
                               "version": 2, "chunks": 3}
    assert calls == [("runbook.md", "upload")]


# --- GET /api/documents -------------------------------------------------------

def test_list_defaults(monkeypatch):
    calls = []

    def fake_list(conn, source, limit, offset):
        calls.append((source, limit, offset))
        return 1, [document()]

    monkeypatch.setattr(ingest, "list_documents", fake_list)
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["documents"][0]["id"] == str(DOC_ID)
    assert calls == [(None, 50, 0)]  # None: every source but HotpotQA


def test_list_rejects_limit_over_200(monkeypatch):
    monkeypatch.setattr(ingest, "list_documents", not_called)
    assert client.get("/api/documents?limit=201").status_code == 422


# --- DELETE /api/documents/{id} -----------------------------------------------

def test_delete_protected_is_403(monkeypatch):
    monkeypatch.setattr(ingest, "get_document", lambda conn, document_id: document(is_protected=True))
    monkeypatch.setattr(ingest, "delete_document", not_called)
    assert client.delete(f"/api/documents/{DOC_ID}").status_code == 403


def test_delete_missing_is_404(monkeypatch):
    monkeypatch.setattr(ingest, "get_document", lambda conn, document_id: None)
    monkeypatch.setattr(ingest, "delete_document", not_called)
    assert client.delete(f"/api/documents/{DOC_ID}").status_code == 404


def test_delete_returns_the_id(monkeypatch):
    deleted = []
    monkeypatch.setattr(ingest, "get_document", lambda conn, document_id: document())
    monkeypatch.setattr(ingest, "delete_document", lambda conn, document_id: deleted.append(document_id) or True)
    response = client.delete(f"/api/documents/{DOC_ID}")
    assert response.status_code == 200
    assert response.json() == {"deleted": str(DOC_ID)}
    assert deleted == [DOC_ID]


def test_delete_needs_a_uuid():
    assert client.delete("/api/documents/not-a-uuid").status_code == 422


# --- POST /api/ask ------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"question": "What failed?", "mode": "turbo"},
    {"question": "   "},
    {"question": "x" * 1001},
])
def test_bad_ask_body_is_422(monkeypatch, body):
    monkeypatch.setattr(answer, "answer_question", not_called)
    monkeypatch.setattr(agent, "run_agent", not_called)
    assert client.post("/api/ask", json=body).status_code == 422


def test_simple_ask_returns_the_answer_json(monkeypatch):
    questions = []
    monkeypatch.setattr(answer, "answer_question", lambda conn, question: questions.append(question) or ANSWER)
    monkeypatch.setattr(agent, "run_agent", not_called)
    response = client.post("/api/ask", json={"question": "  What failed in March?  "})
    assert response.status_code == 200
    assert response.json() == ANSWER
    assert questions == ["What failed in March?"]  # stripped


def test_agent_ask_returns_the_answer_without_the_trace(monkeypatch):
    monkeypatch.setattr(agent, "run_agent", lambda conn, question: (ANSWER, {"rounds": 2, "searches": []}))
    monkeypatch.setattr(answer, "answer_question", not_called)
    response = client.post("/api/ask", json={"question": "What failed in March?", "mode": "agent"})
    assert response.status_code == 200
    assert response.json() == ANSWER


def test_llm_failure_is_503_with_a_friendly_message(monkeypatch):
    def fail(conn, question):
        raise LLMUnavailable(FRIENDLY_MESSAGE)

    monkeypatch.setattr(answer, "answer_question", fail)
    response = client.post("/api/ask", json={"question": "What failed in March?"})
    assert response.status_code == 503
    assert response.json() == {"detail": FRIENDLY_MESSAGE}


def test_database_down_is_503(monkeypatch):
    def fail():
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(db, "get_conn", fail)
    response = client.get("/api/documents")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unreachable"}
