"""Central configuration, loaded from the .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-flash-latest")
EMBED_MODEL = os.getenv("EMBED_MODEL", "models/gemini-embedding-001")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

DATA_DIR = ROOT_DIR / "data"
MENU_FILE = DATA_DIR / "menu.json"
INFO_FILES = [DATA_DIR / "policies.md", DATA_DIR / "faq.md"]
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is missing. Copy .env.example to .env and add your Gemini API key.")
