"""Shared environment configuration, loaded before clients are initialized."""

import os

from dotenv import load_dotenv

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
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
