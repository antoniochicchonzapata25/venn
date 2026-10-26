"""Create (or reset) the local database and the demo user.

Usage (from the repository root):
    python scripts/seed.py           # migrate + add the demo user if missing
    python scripts/seed.py --reset   # delete the local SQLite file first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import make_engine, make_session_factory  # noqa: E402
from app.migrations import upgrade_to_head  # noqa: E402
from app.seed import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_nutrition, ensure_demo_training, ensure_demo_user
from app.services.catalog import ensure_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete the local SQLite database first")
    args = parser.parse_args()

    url = get_settings().database_url
    if args.reset:
        if not url.startswith("sqlite:///"):
            print("--reset only works with the default SQLite database.")
            return 1
        db_file = Path(url.removeprefix("sqlite:///"))
        db_file.unlink(missing_ok=True)
        print(f"Deleted {db_file}")

    upgrade_to_head(url)
    engine = make_engine(url)
    with make_session_factory(engine)() as db:
        loaded = ensure_catalog(db)
        _, created = ensure_demo_user(db)
        entries = ensure_demo_nutrition(db)
        sessions = ensure_demo_training(db)
    engine.dispose()
    print(f"Food catalog {'loaded' if loaded else 'already up to date'}; demo food entries added: {entries}; demo workouts added: {sessions}.")
    print(f"Database ready. Demo user {'created' if created else 'already exists'}: "
          f"username '{DEMO_USERNAME}', password '{DEMO_PASSWORD}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
