"""Shared environment configuration, loaded before clients are initialized."""

import os

from dotenv import load_dotenv

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/line_math")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID", "")
LINE_PROVIDER_ID = os.getenv("LINE_PROVIDER_ID", "")
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID", "")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
FILE_STORAGE_ROOT = os.getenv("FILE_STORAGE_ROOT", "/tmp/line-math-files")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "auto")
S3_ADDRESSING_STYLE = os.getenv("S3_ADDRESSING_STYLE", "virtual")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
EMBEDDINGS_ENABLED = os.getenv("EMBEDDINGS_ENABLED", "false").lower() == "true"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"
MAX_DAILY_AI_REQUESTS = int(os.getenv("MAX_DAILY_AI_REQUESTS", "100"))
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "90"))
MAX_JOB_ATTEMPTS = int(os.getenv("MAX_JOB_ATTEMPTS", "3"))
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,https://localhost:3000,"
        "http://127.0.0.1:3000,https://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
