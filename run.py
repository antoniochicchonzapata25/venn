"""Start Venn: migrate the database, make sure the demo user exists, and serve the app.

Usage (from the repository root, with the virtual environment active):
    python run.py              # http://127.0.0.1:8000
    python run.py --port 8010
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import uvicorn  # noqa: E402

from app.branding import APP_NAME  # noqa: E402
from app.config import FRONTEND_DIST, get_settings, load_env_files  # noqa: E402
from app.db import make_engine, make_session_factory  # noqa: E402
from app.migrations import upgrade_to_head  # noqa: E402
from app.seed import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_nutrition, ensure_demo_training, ensure_demo_user
from app.services.catalog import ensure_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    env_files = load_env_files()
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    engine = make_engine(settings.database_url)
    with make_session_factory(engine)() as db:
        ensure_catalog(db)
        ensure_demo_user(db)
        ensure_demo_nutrition(db)
        ensure_demo_training(db)
    engine.dispose()

    print(f"\n{APP_NAME} is starting at http://{args.host}:{args.port}")
    print(f"  Demo login: {DEMO_USERNAME} / {DEMO_PASSWORD}")
    print(f"  .env files loaded: {', '.join(str(p) for p in env_files) or 'none'}")
    print(f"  AI: {'configured (' + settings.model_name + ')' if settings.ai_configured else 'disabled (no PORTKEY_API_KEY)'}")
    if not (FRONTEND_DIST / "index.html").is_file():
        print("  Warning: frontend/dist is missing; only the API will be available.")
    print("  Press Ctrl+C to stop.\n")

    from app.main import create_app
    uvicorn.run(create_app(run_migrations=False), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
