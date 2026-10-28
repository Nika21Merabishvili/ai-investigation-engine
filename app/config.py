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

# LLM: Gemini through its OpenAI-compatible endpoint. Key and model ID come from the environment.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_TIMEOUT_SECONDS = 30.0
LLM_RETRY_WAITS = (2, 4, 8)  # seconds to wait before retry 1, 2 and 3

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # POST /api/documents answers 413 above this

# If the best chunk's cosine similarity is below this, answer "insufficient" without calling the LLM.
# 0.0 switches the check off until Step 6 picks a real value.
MIN_DENSE_SIMILARITY = float(os.getenv("MIN_DENSE_SIMILARITY", "0.0"))