# app/db.py
import psycopg

from app import config


def get_conn() -> psycopg.Connection:
    """Open a new connection. Use as: with get_conn() as conn: ..."""
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (check .env / .env.neon or Render env vars)")
    return psycopg.connect(config.DATABASE_URL, connect_timeout=10)


def ping() -> None:
    """Run SELECT 1. Raises psycopg.OperationalError if the database is unreachable."""
    with get_conn() as conn:
        conn.execute("SELECT 1")