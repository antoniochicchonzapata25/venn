"""Authentication and backend-enforced user-data isolation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User, UserSession
from tests.conftest import VALID_PROFILE, register

PROTECTED = [
    ("get", "/api/auth/me"), ("get", "/api/profile"), ("put", "/api/profile"),
    ("get", "/api/targets/current"), ("get", "/api/targets/preview"), ("post", "/api/targets/recalculate"),
    ("post", "/api/targets/manual"), ("get", "/api/targets/history"), ("get", "/api/targets/1"),
    ("get", "/api/limitations"), ("post", "/api/limitations"), ("put", "/api/limitations/1"),
    ("delete", "/api/limitations/1"), ("post", "/api/health/ai"),
]


# --- authentication -------------------------------------------------------------------

def test_register_login_logout_cycle(client: TestClient):
    me = register(client, "casey")
    assert me["username"] == "casey"
    cookie = client.cookies.get("venn_session")
    assert cookie
    assert client.get("/api/auth/me").json()["username"] == "casey"

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    # the old token is dead server-side, even if someone kept a copy
    client.cookies.set("venn_session", cookie)
    assert client.get("/api/auth/me").status_code == 401

    r = client.post("/api/auth/login", json={"username": "casey", "password": "correct-horse-1"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_session_cookie_is_http_only(client: TestClient):
    r = client.post("/api/auth/register", json={"username": "dana", "password": "long-enough-1"})
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header


def test_password_is_hashed_and_session_token_not_stored(client: TestClient, app):
    register(client, "erin", "my-secret-pass")
    token = client.cookies.get("venn_session")
    with app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "erin"))
        assert user.password_hash.startswith("$argon2") and "my-secret-pass" not in user.password_hash
        stored = db.scalar(select(UserSession.token_hash).where(UserSession.user_id == user.id))
        assert stored != token and len(stored) == 64


def test_wrong_password_and_unknown_user_get_the_same_answer(client: TestClient):
    register(client, "frank")
    client.post("/api/auth/logout")
    a = client.post("/api/auth/login", json={"username": "frank", "password": "nope-nope-1"})
    b = client.post("/api/auth/login", json={"username": "ghost", "password": "nope-nope-1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_login_is_throttled_after_five_failures(client: TestClient):
    register(client, "gina")
    client.post("/api/auth/logout")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "gina", "password": "bad-password"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "gina", "password": "correct-horse-1"})
    assert r.status_code == 429


def test_registration_validation(client: TestClient):
    assert client.post("/api/auth/register", json={"username": "ab", "password": "long-enough"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "Bad Name!", "password": "long-enough"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "shorty", "password": "short"}).status_code == 422
    register(client, "henry")
    dup = client.post("/api/auth/register", json={"username": "HENRY", "password": "long-enough-2"})
    assert dup.status_code == 409


def test_every_protected_route_requires_login(client: TestClient):
    for method, path in PROTECTED:
        r = getattr(client, method)(path) if method in ("get", "delete") else getattr(client, method)(path, json={})
        assert r.status_code == 401, f"{method.upper()} {path} returned {r.status_code}"


def test_forged_cookie_is_rejected(client: TestClient):
    client.cookies.set("venn_session", "forged-token-value")
    assert client.get("/api/profile").status_code == 401


# --- isolation between users ----------------------------------------------------------

def test_profiles_are_isolated(two_users):
    alice, bob = two_users
    assert alice.put("/api/profile", json=VALID_PROFILE).status_code == 200
    bob_profile = bob.get("/api/profile").json()
    assert bob_profile["is_complete"] is False and bob_profile["weight_kg"] is None
    # Bob's update cannot touch Alice's row
    assert bob.put("/api/profile", json={**VALID_PROFILE, "weight_kg": 99}).status_code == 200
    assert alice.get("/api/profile").json()["weight_kg"] == 60


def test_profile_body_cannot_smuggle_a_user_id(two_users):
    alice, _ = two_users
    r = alice.put("/api/profile", json={**VALID_PROFILE, "user_id": 2})
    assert r.status_code == 422  # unknown fields are rejected outright


def test_targets_are_isolated_by_id(two_users):
    alice, bob = two_users
    alice.put("/api/profile", json=VALID_PROFILE)
    alice_target = alice.get("/api/targets/current").json()["target"]
    assert alice.get(f"/api/targets/{alice_target['id']}").status_code == 200
    # Bob guesses Alice's target id
    assert bob.get(f"/api/targets/{alice_target['id']}").status_code == 404
    assert bob.get("/api/targets/current").json()["target"] is None
    assert bob.get("/api/targets/history").json() == []


def test_limitations_are_isolated(two_users):
    alice, bob = two_users
    created = alice.post("/api/limitations", json={"body_area": "knee", "kind": "temporary", "note": "sore"}).json()
    lid = created["id"]
    assert bob.get("/api/limitations").json() == []
    upd = {"body_area": "knee", "kind": "ongoing", "severity": "avoid", "note": "hacked"}
    assert bob.put(f"/api/limitations/{lid}", json=upd).status_code == 404
    assert bob.delete(f"/api/limitations/{lid}").status_code == 404
    still = alice.get("/api/limitations").json()
    assert len(still) == 1 and still[0]["note"] == "sore"
