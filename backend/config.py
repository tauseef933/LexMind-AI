"""
Central config — loads .env and resolves project paths regardless of cwd.

Import this module before any code that reads os.environ for paths/keys.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent
_parent = BACKEND_ROOT.parent
# Monorepo: repo root sits above backend/; Railway deploys backend/ as /app
if (_parent / "frontend").is_dir() or (_parent / "Procfile").is_file():
    PROJECT_ROOT = _parent
else:
    PROJECT_ROOT = BACKEND_ROOT

# Load backend/.env first, then project-root .env (root overrides)
for _env_file in (BACKEND_ROOT / ".env", PROJECT_ROOT / ".env"):
    if _env_file.is_file():
        load_dotenv(_env_file, override=True)

UPLOADS_DIR = PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _abs_sqlite_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./lexmind.db")
    if url.startswith("sqlite:///./"):
        rel = url.removeprefix("sqlite:///./")
        db_path = (PROJECT_ROOT / rel).resolve()
        return f"sqlite:///{db_path.as_posix()}"
    return url


def _abs_chroma_path() -> str:
    raw = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
    p = Path(raw)
    if not p.is_absolute():
        p = (PROJECT_ROOT / raw).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


# Normalise paths so cwd never matters
os.environ["DATABASE_URL"] = _abs_sqlite_url()
os.environ["CHROMA_PERSIST_PATH"] = _abs_chroma_path()

# Groq LLM — llama-3.1-70b-versatile was decommissioned; use 3.3 or override via env
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Placeholder SECRET_KEY disables auth in local dev
_PLACEHOLDER_SECRETS = {"", "your-random-secret-key-here", "change-me"}


def auth_enabled() -> bool:
    key = os.getenv("SECRET_KEY", "").strip()
    return bool(key) and key not in _PLACEHOLDER_SECRETS


def get_secret_key() -> str:
    return os.getenv("SECRET_KEY", "").strip()
