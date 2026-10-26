"""Shared fixtures. Every test runs offline: real network connections are blocked."""

from __future__ import annotations

import shutil
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config

FAKE_KEY = "pk-test-NOT-A-REAL-KEY-7f3a9c"


class NetworkBlocked(ConnectionRefusedError):
    pass


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block every non-loopback connection. (On Windows the event loop needs a loopback socketpair.)"""
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def _check(address) -> None:  # noqa: ANN001
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOOPBACK:
            raise NetworkBlocked(f"Tests must not open network connections (tried {host}).")

    def connect(self, address):  # noqa: ANN001
        _check(address)
        return real_connect(self, address)

    def connect_ex(self, address):  # noqa: ANN001
        _check(address)
        return real_connect_ex(self, address)

    def create_connection(address, *_args, **_kwargs):  # noqa: ANN001
        _check(address)
        raise NetworkBlocked("Tests must not open network connections.")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ignore real .env files and keys on this machine; start every test with AI disabled."""
    monkeypatch.setattr(config, "ENV_FILE_LOCATIONS", ())
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture(scope="session")
def template_db(tmp_path_factory) -> Path:
    """Migrated database with the full bundled food catalog, built once and copied per test."""
    from app.db import make_engine, make_session_factory
    from app.migrations import upgrade_to_head
    from app.services.catalog import ensure_catalog

    path = tmp_path_factory.mktemp("template") / "template.db"
    url = f"sqlite:///{path.as_posix()}"
    upgrade_to_head(url)
    engine = make_engine(url)
    with make_session_factory(engine)() as db:
        ensure_catalog(db)
    engine.dispose()
    return path


@pytest.fixture
def db_url(tmp_path, template_db) -> str:
    target = tmp_path / "test.db"
    shutil.copyfile(template_db, target)
    return f"sqlite:///{target.as_posix()}"


@pytest.fixture
def empty_db_url(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"


@pytest.fixture
def app(db_url, tmp_path):
    from app.main import create_app

    return create_app(database_url=db_url, frontend_dist=tmp_path / "no-dist")


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


VALID_PROFILE = {
    "sex": "female", "birth_year": 1995, "height_cm": 165, "weight_kg": 60,
    "activity_level": "light", "goal": "maintain", "goal_rate_pct": 0,
    "protein_level": "standard", "diet_style": "balanced", "dietary_preferences": ["vegetarian"],
    "training_goal": "general_fitness", "experience": "beginner", "days_per_week": 3,
    "session_minutes": 45, "equipment": ["dumbbell", "body only"], "preferred_split": "full_body", "units": "metric",
}


def register(client: TestClient, username: str, password: str = "correct-horse-1") -> dict:
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def two_users(app) -> Iterator[tuple[TestClient, TestClient]]:
    """Two independent browsers, each logged in as a different user, sharing one database."""
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "alice")
        register(bob, "bob")
        yield alice, bob
