"""scripts/create_indexes.py

Run indexes.sql after a bulk load, against the local database or Neon.
Run from the repo root:
    python -m scripts.create_indexes             # local (.env)
    python -m scripts.create_indexes .env.neon   # Neon
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg

parser = argparse.ArgumentParser(description="Create the search indexes (run after a bulk load).")
parser.add_argument("env_file", nargs="?", help="default .env (local); .env.neon for Neon")
args = parser.parse_args()

# config.py reads ENV_FILE at import time, so it must be set before importing app.
if args.env_file:
    if not Path(args.env_file).is_file():
        sys.exit(f"Env file not found: {args.env_file}")
    os.environ["ENV_FILE"] = args.env_file

from app.config import DATABASE_URL  # noqa: E402

sql = Path("indexes.sql").read_text(encoding="utf-8")

# One transaction: SET LOCAL applies to the CREATE INDEX lines, even through Neon's pooler.
with psycopg.connect(DATABASE_URL) as conn:
    print(f"Creating indexes on {conn.info.dbname} at {conn.info.host} (HNSW can take a few minutes) ...")
    conn.execute(sql)  # several statements in one execute() are fine when there are no parameters
    rows = conn.execute(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'chunks' ORDER BY indexname"
    ).fetchall()
    conn.commit()

print("Indexes on chunks:", ", ".join(name for (name,) in rows))
