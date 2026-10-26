# app/main.py
import logging

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import db

log = logging.getLogger(__name__)
app = FastAPI(title="AI Investigation Engine")


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