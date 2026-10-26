"""Health checks, AI-disabled mode, secret handling, migrations, seed data and static serving."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select

from app import config
from app.ai import client as ai_client
from app.db import Base, make_engine, make_session_factory
from app.migrations import upgrade_to_head
from app.models import AiUsage, NutritionTarget, TrainingLimitation
from app.seed import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_user
from tests.conftest import FAKE_KEY, NetworkBlocked, register


def test_health_works_without_ai_key(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["app"] == "Venn" and h["database"] == "ok"
    assert h["ai"]["configured"] is False
    assert "disabled" in h["ai"]["message"]


def test_live_ai_check_reports_disabled_without_key(client):
    register(client, "pat")
    r = client.post("/api/health/ai").json()
    assert r["status"] == "disabled" and r["model"] == "gpt-6-luna"


def test_ai_check_records_token_usage_and_is_cached(client, app, monkeypatch):
    monkeypatch.setenv("PORTKEY_API_KEY", FAKE_KEY)
    config.get_settings.cache_clear()
    calls = []

    def fake_check():
        calls.append(1)
        return ai_client.AiCallResult(status="ok", model="gpt-6-luna", served_model="gpt-6-luna-2026-09-22",
                                      latency_ms=640, input_tokens=11, output_tokens=5)

    monkeypatch.setattr(ai_client, "check_connection", fake_check)
    register(client, "quinn")
    first = client.post("/api/health/ai").json()
    second = client.post("/api/health/ai").json()
    assert first["status"] == "ok" and first["usage"]["input_tokens"] == 11 and first["cached"] is False
    assert second["cached"] is True and len(calls) == 1
    assert first["estimated_cost_usd"] == pytest.approx(3.6e-6) and "class slide" in first["price_source"]
    with app.state.session_factory() as db:
        rows = db.scalars(select(AiUsage)).all()
        assert len(rows) == 1 and rows[0].output_tokens == 5 and rows[0].purpose == "health_check"


def test_real_check_without_network_fails_cleanly_and_never_leaks_key(client, monkeypatch):
    """With a (fake) key but no network, the check returns an error message, not a crash or the key."""
    monkeypatch.setenv("PORTKEY_API_KEY", FAKE_KEY)
    config.get_settings.cache_clear()
    register(client, "rae")
    r = client.post("/api/health/ai")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error" and body["message"]
    assert FAKE_KEY not in r.text
    assert FAKE_KEY not in client.get("/api/health").text


def test_network_guard_is_active():
    import socket
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("example.com", 443))


def test_only_gpt_6_luna_is_used():
    assert config.get_settings().model_name == "gpt-6-luna"


def test_env_lookup_is_repo_then_parent(tmp_path, monkeypatch):
    repo = tmp_path / "submissions" / "venn"
    repo.mkdir(parents=True)
    (repo.parent / ".env").write_text("PORTKEY_API_KEY=from-parent\n")
    monkeypatch.setattr(config, "ENV_FILE_LOCATIONS", (repo / ".env", repo.parent / ".env"))
    assert config.load_env_files() == [repo.parent / ".env"]
    import os
    assert os.environ["PORTKEY_API_KEY"] == "from-parent"
    (repo / ".env").write_text("PORTKEY_API_KEY=from-repo\n")
    monkeypatch.delenv("PORTKEY_API_KEY")
    config.load_env_files()
    assert os.environ["PORTKEY_API_KEY"] == "from-repo"


def test_migrations_match_models(empty_db_url):
    upgrade_to_head(empty_db_url)
    engine = make_engine(empty_db_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_seed_is_idempotent_and_demo_can_log_in(client, app):
    with app.state.session_factory() as db:
        user, created = ensure_demo_user(db)
        _, created_again = ensure_demo_user(db)
        assert created and not created_again
        assert db.scalars(select(NutritionTarget).where(NutritionTarget.user_id == user.id)).all()
        assert db.scalars(select(TrainingLimitation).where(TrainingLimitation.user_id == user.id)).all()
    r = client.post("/api/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    assert r.status_code == 200
    assert client.get("/api/profile").json()["is_complete"] is True


def test_frontend_is_served_with_spa_fallback(tmp_path, db_url):
    from fastapi.testclient import TestClient

    from app.main import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>Venn app</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    with TestClient(create_app(database_url=db_url, frontend_dist=dist)) as c:
        assert "Venn app" in c.get("/").text
        assert "Venn app" in c.get("/settings").text  # client-side route
        assert c.get("/assets/app.js").status_code == 200
        assert c.get("/api/does-not-exist").status_code == 404
        assert c.get("/../.env").status_code in (200, 404) and "PORTKEY" not in c.get("/../.env").text


def test_session_factory_helper(empty_db_url):
    upgrade_to_head(empty_db_url)
    engine = make_engine(empty_db_url)
    with make_session_factory(engine)() as db:
        assert db.execute(select(1)).scalar() == 1
    engine.dispose()
