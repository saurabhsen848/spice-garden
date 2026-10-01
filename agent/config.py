"""Application configuration from environment, Streamlit secrets, and local .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
# Streamlit Cloud environment variables take precedence; local development can use .env.
load_dotenv(ROOT_DIR / ".env", override=False)


def _streamlit_secrets():
    try:
        import streamlit as st
        return st.secrets
    except Exception:  # secrets are unavailable outside Streamlit or when unset
        return {}


def _configured_value(name: str, default: str | None = None, *, environ=None, secrets=None) -> str | None:
    """Resolve a setting without logging its value: environment, Streamlit secrets, default."""
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if value:
        return value
    if secrets is None:
        secrets = _streamlit_secrets()
    try:
        value = secrets.get(name)
    except Exception:  # Streamlit raises when no secrets file is configured locally
        value = None
    return value or default


GOOGLE_API_KEY = _configured_value("GOOGLE_API_KEY")
CHAT_MODEL = _configured_value("CHAT_MODEL", "gemini-flash-latest")
EMBED_MODEL = _configured_value("EMBED_MODEL", "models/gemini-embedding-001")
API_BASE_URL = (_configured_value("API_BASE_URL", "http://127.0.0.1:8000") or "").rstrip("/")

DATA_DIR = ROOT_DIR / "data"
MENU_FILE = DATA_DIR / "menu.json"
INFO_FILES = [DATA_DIR / "policies.md", DATA_DIR / "faq.md"]
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"


def require_google_api_key() -> str:
    """Return the configured key or raise a safe, actionable configuration error."""
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your-gemini-api-key-here":
        raise RuntimeError(
            "GOOGLE_API_KEY is not configured. Set it as an environment variable or Streamlit secret; "
            "use .env for local development."
        )
    return GOOGLE_API_KEY
