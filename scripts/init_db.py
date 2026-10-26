# scripts/init_db.py
"""Create the tables from schema.sql. Safe to run more than once.

Run from the repo root:
    python -m scripts.init_db              # local database (.env)
    python -m scripts.init_db .env.neon    # Neon
"""
import os
import sys
from pathlib import Path

# config.py reads ENV_FILE at import time, so it must be set before importing app.
if len(sys.argv) > 1:
    env_file = sys.argv[1]
    if not Path(env_file).is_file():
        sys.exit(f"Env file not found: {env_file}")
    os.environ["ENV_FILE"] = env_file

from app import db  # noqa: E402  (import must come after ENV_FILE is set)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def main() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with db.get_conn() as conn:  # commits at the end of the block, rolls back on error
        print(f"Database: {conn.info.dbname} on {conn.info.host}")
        conn.execute(sql)  # no parameters, so several statements in one call are allowed
        vector_version = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()[0]
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        ]
    print(f"pgvector {vector_version}; tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
