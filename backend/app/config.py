"""Runtime settings, read once from the environment and `.env` files.

`.env` is looked up in exactly two places, as the course requires:
first this repository's folder, then the folder one level above it.
The Portkey key is loaded into the process environment but is never logged,
returned by an API route, or stored anywhere else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
ENV_FILE_LOCATIONS = (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env")

# The course key may only be used with gpt-6-luna. No silent substitution.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
AI_TIMEOUT_SECONDS = 30


def load_env_files() -> list[Path]:
    """Load the repo `.env`, then the parent-folder `.env`. Earlier files win."""
    loaded = []
    for env_file in ENV_FILE_LOCATIONS:
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            loaded.append(env_file)
    return loaded


def _resolve_database_url(raw: str | None) -> str:
    """Relative SQLite paths are resolved against the project root, not the cwd."""
    prefix = "sqlite:///"
    if not raw:
        raw = "sqlite:///data/venn.db"
    if raw.startswith(prefix) and raw != "sqlite:///:memory:":
        path = Path(raw[len(prefix):])
        if not path.is_absolute():
            return f"{prefix}{(PROJECT_ROOT / path).as_posix()}"
    return raw


@dataclass(frozen=True)
class Settings:
    database_url: str
    cookie_secure: bool
    model_name: str = MODEL_NAME
    session_days: int = 14

    @property
    def portkey_api_key(self) -> str:
        return os.getenv("PORTKEY_API_KEY", "").strip()

    @property
    def ai_configured(self) -> bool:
        key = self.portkey_api_key
        return bool(key) and key != "your-portkey-key-here"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env_files()
    return Settings(
        database_url=_resolve_database_url(os.getenv("DATABASE_URL", "").strip() or None),
        cookie_secure=os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"},
    )
