"""Profile, targets and limitations through the API."""

from __future__ import annotations

from datetime import date

from tests.conftest import VALID_PROFILE, register


def test_new_user_starts_with_incomplete_profile(client):
    register(client, "ivy")
    p = client.get("/api/profile").json()
    assert p["is_complete"] is False
    assert client.get("/api/targets/preview").status_code == 409
    assert client.post("/api/targets/recalculate").status_code == 409


def test_saving_profile_creates_formula_target_with_breakdown(client):
    register(client, "jay")
    r = client.put("/api/profile", json=VALID_PROFILE)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["is_complete"] and body["target_updated"]
    t = body["target"]
    assert t["method"] == "formula"
    assert {"bmr", "tdee", "activity_multiplier", "minimum_kcal", "warnings", "inputs"} <= t["breakdown"].keys()
    assert body["profile"]["dietary_preferences"] == ["vegetarian"]


def test_manual_target_is_kept_when_profile_changes(client):
    register(client, "kim")
    client.put("/api/profile", json=VALID_PROFILE)
    manual = {"kcal": 2000, "protein_g": 150, "carb_g": 200, "fat_g": 67}
    assert client.post("/api/targets/manual", json=manual).status_code == 201
    r = client.put("/api/profile", json={**VALID_PROFILE, "weight_kg": 62}).json()
    assert r["target_updated"] is False and r["target"]["method"] == "manual"
    # explicit recalculation switches back to the formula
    assert client.post("/api/targets/recalculate").json()["method"] == "formula"
    assert len(client.get("/api/targets/history").json()) == 3


def test_manual_target_below_safety_minimum_is_rejected(client):
    register(client, "lee")
    client.put("/api/profile", json=VALID_PROFILE)  # female -> 1,200 kcal minimum
    r = client.post("/api/targets/manual", json={"kcal": 1000, "protein_g": 80, "carb_g": 100, "fat_g": 31})
    assert r.status_code == 422
    assert any("1200" in e for e in r.json()["detail"])
    assert client.get("/api/targets/current").json()["target"]["method"] == "formula"


def test_profile_validation_errors(client):
    register(client, "max")
    this_year = date.today().year
    bad = [
        {"birth_year": this_year - 15},           # minor
        {"weight_kg": 10},                        # out of range
        {"goal": "lose", "goal_rate_pct": 2.0},   # too fast
        {"goal": "gain", "goal_rate_pct": 1.0},   # too fast
        {"days_per_week": 8},
        {"session_minutes": 5},
        {"equipment": ["jetpack"]},
        {"dietary_preferences": ["carnivore-only"]},
        {"sex": "other-value"},
    ]
    for change in bad:
        r = client.put("/api/profile", json={**VALID_PROFILE, **change})
        assert r.status_code == 422, change
    assert client.get("/api/profile").json()["is_complete"] is False


def test_maintain_forces_rate_to_zero_and_duplicates_are_removed(client):
    register(client, "nia")
    r = client.put("/api/profile", json={**VALID_PROFILE, "goal": "maintain", "goal_rate_pct": 0.4,
                                         "equipment": ["dumbbell", "dumbbell"]}).json()
    assert r["profile"]["goal_rate_pct"] == 0
    assert r["profile"]["equipment"] == ["dumbbell"]


def test_limitation_crud_and_note_sanitizing(client):
    register(client, "oli")
    r = client.post("/api/limitations", json={"body_area": "lower_back", "kind": "ongoing",
                                              "severity": "avoid", "note": "  disc issue\x00\x07 "})
    assert r.status_code == 201
    lim = r.json()
    assert lim["note"] == "disc issue"
    upd = client.put(f"/api/limitations/{lim['id']}", json={**{k: lim[k] for k in ("body_area", "kind", "severity", "note")},
                                                             "active": False}).json()
    assert upd["active"] is False
    assert client.post("/api/limitations", json={"body_area": "spleen", "kind": "ongoing"}).status_code == 422
    assert client.post("/api/limitations", json={"body_area": "knee", "kind": "ongoing", "note": "x" * 281}).status_code == 422
    assert client.delete(f"/api/limitations/{lim['id']}").status_code == 204
    assert client.get("/api/limitations").json() == []


def test_options_and_disclaimer(client):
    o = client.get("/api/options").json()
    assert "barbell" in o["equipment"] and "not medical advice" in o["disclaimer"]
