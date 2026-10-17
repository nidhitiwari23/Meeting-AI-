"""Central configuration: paths, secrets lookup and default thresholds.

Secrets are looked up in this order:
1. values typed by the user in Settings (kept only in the browser session)
2. Streamlit secrets (``.streamlit/secrets.toml`` locally, the "Secrets" box on Streamlit Cloud)
3. environment variables (``.env`` is loaded if python-dotenv is installed)
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MEETINGAI_DATA", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
CHROMA_DIR = DATA_DIR / "chroma"
DB_PATH = DATA_DIR / "meetingai.db"

for _d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

try:  # optional
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:  # pragma: no cover
    pass

APP_NAME = "MeetingAI"
SUPPORTED_AUDIO = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "wma", "webm"]
SUPPORTED_VIDEO = ["mp4", "mov", "mkv", "avi", "webm"]
SUPPORTED_TEXT = ["txt", "vtt", "srt", "md", "docx", "pdf"]
MAX_UPLOAD_MB = 200

# Default confidence-gateway thresholds (editable in Settings, stored in the DB)
DEFAULT_THRESHOLDS = {
    "cls_threshold": 0.80,   # min confidence to accept a classical classification
    "cls_margin": 0.15,      # min gap between best and second-best class
    "owner_threshold": 0.85,  # min confidence to accept a classical owner
    "deadline_threshold": 0.85,  # min confidence to accept a classical deadline
    "retrieval_min_score": 0.28,  # below this similarity we say "not found"
}

DEFAULT_MODELS = {
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "GROQ_FAST_MODEL": "llama-3.1-8b-instant",
    "GROQ_WHISPER_MODEL": "whisper-large-v3-turbo",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GEMINI_FAST_MODEL": "gemini-2.5-flash-lite",
    "OPENROUTER_MODEL": "meta-llama/llama-3.3-70b-instruct:free",
}


_secrets_cache: dict = {}


def _secrets_file_exists() -> bool:
    if "v" not in _secrets_cache:
        paths = [Path.home() / ".streamlit" / "secrets.toml", Path.cwd() / ".streamlit" / "secrets.toml", ROOT / ".streamlit" / "secrets.toml"]
        _secrets_cache["v"] = any(p.exists() for p in paths)
    return _secrets_cache["v"]


def secret(name: str, default: str | None = None) -> str | None:
    """Return a configuration value (see module docstring for the lookup order)."""
    try:
        import streamlit as st

        override = st.session_state.get("_session_keys", {}).get(name)
        if override:
            return override
        try:
            # touching st.secrets without a secrets file makes Streamlit show a red banner, so check first
            if _secrets_file_exists() and name in st.secrets:
                value = st.secrets[name]
                if value not in (None, ""):
                    return str(value)
        except Exception:
            pass
    except Exception:
        pass
    value = os.environ.get(name)
    if value:
        return value
    return DEFAULT_MODELS.get(name, default)


def set_session_key(name: str, value: str) -> None:
    import streamlit as st

    keys = st.session_state.setdefault("_session_keys", {})
    if value:
        keys[name] = value.strip()
    else:
        keys.pop(name, None)
