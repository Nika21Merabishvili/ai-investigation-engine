# app/config.py
import os

from dotenv import load_dotenv

# Locally: loads .env, or the file named in ENV_FILE (e.g. ENV_FILE=.env.neon).
# In Docker/Render no .env file exists, so this does nothing and the real
# environment variables are used. load_dotenv never overrides variables already set.
load_dotenv(os.getenv("ENV_FILE", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL", "")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
MODEL_CACHE_DIR = "models"