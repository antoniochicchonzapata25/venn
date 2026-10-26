"""Training Core: generation rules, limitations, duration, replacement, logging lifecycle, isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app import config
from app.models import Workout
from app.services.exercises import catalog
from app.services.workout_generator import GenerationError, History, generate
from app.services.workout_rules import (
    Limitation, TrainingContext, check_exercise, estimate_seconds, exercise_seconds, validate_plan,
)
from tests.conftest import VALID_PROFILE, register

GYM = frozenset({"barbell", "dumbbell", "cable", "machine", "bench", "pull-up bar"})
TRAINING_PROFILE = {**VALID_PROFILE, "training_goal": "build_muscle", "experience": "intermediate", "days_per_week": 4,
                    "session_minutes": 60, "equipment": sorted(GYM), "preferred_split": "auto"}


def ctx(**kw) -> TrainingContext:
    base = dict(equipment=GYM, limitations=(), experience="intermediate", goal="build_muscle", budget_minutes=75)
    return TrainingContext(**{**base, **kw})


def gen(c: TrainingContext, day: str | None = "upper", split: str = "upper_lower", **kw):
    return generate(ctx=c, preferred_split=split, days_per_week=4, history=kw.pop("history", History()), day_type=day, **kw)


# --- generation rules (pure) ----------------------------------------------------------------

def test_generates_complete_valid_routine_within_budget():
    plan = gen(ctx())
    assert plan.name == "Upper Body" and len(plan.items) >= 5
    assert plan.est_seconds <= 75 * 60
    assert [i.role for i in plan.items][:2] == ["main", "main"]
    assert all(i.sets >= 2 and i.rest_s > 0 and i.exercise.instructions for i in plan.items)
    assert validate_plan([i.as_rule_item() for i in plan.items], ctx()) == []
    assert any("not medical advice" in line for line in plan.explanation)


def test_split_follows_days_per_week_and_preference():
    assert generate(ctx=ctx(), preferred_split="auto", days_per_week=3, history=History()).day_type == "full_body"
    assert generate(ctx=ctx(), preferred_split="auto", days_per_week=6, history=History()).split == "push_pull_legs"
    rotated = generate(ctx=ctx(), preferred_split="upper_lower", days_per_week=4,
                       history=History(completed_by_split={"upper_lower": 1}))
    assert rotated.day_type == "lower"


def test_equipment_restrictions_are_enforced():
    home = ctx(equipment=frozenset({"dumbbell"}))  # dumbbells only, no bench
    plan = gen(home)
    for item in plan.items:
        assert set(item.exercise.equipment) <= {"dumbbell", "body only"}, item.exercise.name
    names = {i.exercise.name for i in plan.items}
    assert "Barbell Bench Press - Medium Grip" not in names and "Dumbbell Bench Press" not in names  # bench needed


def test_bodyweight_only_still_produces_a_routine():
    plan = generate(ctx=ctx(equipment=frozenset()), preferred_split="full_body", days_per_week=3, history=History())
    assert all(i.exercise.equipment == ("body only",) for i in plan.items)


def test_avoid_limitation_excludes_every_exercise_that_loads_the_area():
    c = ctx(limitations=(Limitation("lower_back", "avoid"),))
    for day in ("upper", "lower"):
        for item in gen(c, day).items:
            assert item.exercise.loads.get("lower_back", 0) == 0, item.exercise.name


def test_caution_limitation_excludes_heavy_and_flags_moderate():
    c = ctx(limitations=(Limitation("knee", "caution"),))
    plan = gen(c, "lower")
    assert all(i.exercise.loads.get("knee", 0) < 2 for i in plan.items)
    flagged = [i for i in plan.items if i.exercise.loads.get("knee", 0) == 1]
    assert flagged and all(any("knee" in n for n in i.notes) for i in flagged)
    assert any("knee" in line and "caution" in line for line in plan.explanation)


def test_unmappable_limitation_is_disclosed_not_guessed():
    plan = gen(ctx(limitations=(Limitation("other", "avoid", "old wrist fracture"),)))
    assert any("can't match" in line for line in plan.explanation)


def test_experience_limits_exercise_level():
    beginner = gen(ctx(experience="beginner"), "lower")
    assert all(i.exercise.level == "beginner" for i in beginner.items)


def test_validator_blocks_incompatible_plans():
    c = ctx(equipment=frozenset({"dumbbell"}), limitations=(Limitation("shoulder", "avoid"),))
    bad = [{"exercise_id": "Barbell_Squat", "sets": 3, "rep_high": 10, "target_seconds": None, "rest_s": 90},
           {"exercise_id": "Standing_Military_Press", "sets": 3, "rep_high": 10, "target_seconds": None, "rest_s": 90},
           {"exercise_id": "Made_Up", "sets": 3, "rep_high": 10, "target_seconds": None, "rest_s": 90}]
    v = " | ".join(validate_plan(bad, c))
    assert "needs barbell" in v and "shoulder" in v and "unknown exercise" in v


# --- duration ----------------------------------------------------------------------------

def test_duration_estimate_by_hand():
    # Bench press, 3 sets x 10 reps, 120 s rest: per set 10 x 3 s + 15 s setup = 45 s
    # exercise = 3 x 45 + 2 x 120 = 375 s; workout = 300 warm-up + 120 transition + 375 = 795 s
    bench = catalog()["Barbell_Bench_Press_-_Medium_Grip"]
    assert exercise_seconds(bench, 3, 10, None, 120) == 375
    item = {"exercise_id": bench.id, "sets": 3, "rep_high": 10, "target_seconds": None, "rest_s": 120}
    assert estimate_seconds([item]) == 795
    # unilateral split squat doubles working time: 2 x (10 x 3 + 15) = 90 s per set
    split_squat = catalog()["Split_Squat_with_Dumbbells"]
    assert exercise_seconds(split_squat, 2, 10, None, 60) == 2 * 90 + 60
    # same equipment back-to-back: 60 s changeover instead of 120 s
    db_press = {"exercise_id": "Hammer_Curls", "sets": 1, "rep_high": 10, "target_seconds": None, "rest_s": 60}
    db_curl = {"exercise_id": "Dumbbell_Bicep_Curl", "sets": 1, "rep_high": 10, "target_seconds": None, "rest_s": 60}
    assert estimate_seconds([db_press, db_curl]) == 300 + 120 + 45 + 60 + 45


@pytest.mark.parametrize("minutes", [20, 30, 45, 60, 90])
def test_routine_always_fits_the_budget(minutes):
    for day in ("upper", "lower"):
        plan = gen(ctx(budget_minutes=minutes, goal="get_stronger"), day)
        assert plan.est_seconds <= minutes * 60


def test_impossible_budget_explains_and_offers_alternative():
    with pytest.raises(GenerationError) as err:
        gen(ctx(budget_minutes=8, goal="get_stronger"), "upper")
    assert "minutes" in err.value.message and err.value.alternatives


def test_no_compatible_exercises_explains_alternatives():
    c = ctx(equipment=frozenset(), limitations=tuple(Limitation(a, "avoid") for a in ("shoulder", "elbow", "wrist_hand")))
    with pytest.raises(GenerationError) as err:
        gen(c, "push", split="push_pull_legs")
    assert any("equipment" in a for a in err.value.alternatives)


# --- API lifecycle ------------------------------------------------------------------------

def setup_user(client: TestClient, name: str, **profile) -> None:
    register(client, name)
    assert client.put("/api/profile", json={**TRAINING_PROFILE, **profile}).status_code == 200


def test_generate_requires_complete_profile(client):
    register(client, "nop")
    assert client.post("/api/training/generate", json={}).status_code == 409


def test_generate_without_ai_key_uses_deterministic_generator(client):
    assert not config.get_settings().ai_configured
    setup_user(client, "det")
    w = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    assert w["generator"] == "deterministic-v1" and w["status"] == "planned"
    assert w["planned_minutes"] <= 60 and len(w["exercises"]) >= 4
    assert all(e["instructions"] and e["rest_seconds"] for e in w["exercises"])
    # regenerating discards the unstarted plan
    w2 = client.post("/api/training/generate", json={"day_type": "upper", "variant": 1}).json()
    assert client.get(f"/api/training/workouts/{w['id']}").json()["status"] == "discarded"
    assert w2["status"] == "planned"


def test_generate_reports_unfixable_constraints(client):
    setup_user(client, "tiny", session_minutes=15)
    r = client.post("/api/training/generate", json={"day_type": "upper", "minutes": 15})
    # 15 minutes can hold a short upper session; force failure with avoid-everything limitations instead
    for area in ("shoulder", "elbow", "wrist_hand"):
        client.post("/api/limitations", json={"body_area": area, "kind": "ongoing", "severity": "avoid"})
    client.put("/api/profile", json={**TRAINING_PROFILE, "equipment": [], "session_minutes": 15, "preferred_split": "push_pull_legs"})
    r = client.post("/api/training/generate", json={"day_type": "push"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "cannot_generate"
    assert r.json()["detail"]["alternatives"]


def test_replacement_offers_only_compatible_alternatives_and_validates(client):
    setup_user(client, "swp")
    client.post("/api/limitations", json={"body_area": "lower_back", "kind": "ongoing", "severity": "caution"})
    w = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    row = next(e for e in w["exercises"] if e["pattern"] == "pull_h")
    alts = client.get(f"/api/training/workouts/{w['id']}/exercises/{row['id']}/alternatives").json()["alternatives"]
    assert alts and all(a["id"] != row["exercise_id"] for a in alts)
    ids = {a["id"] for a in alts}
    assert "Bent_Over_Barbell_Row" not in ids  # loads the lower back heavily
    assert all(a["pattern"] in ("pull_h", "pull_v") for a in alts)
    # the backend refuses an incompatible pick even if a client sends it
    bad = client.post(f"/api/training/workouts/{w['id']}/exercises/{row['id']}/replace", json={"exercise_id": "Bent_Over_Barbell_Row"})
    assert bad.status_code == 422 and "lower back" in bad.json()["detail"][0]
    pick = alts[0]["id"]
    after = client.post(f"/api/training/workouts/{w['id']}/exercises/{row['id']}/replace", json={"exercise_id": pick}).json()
    swapped = next(e for e in after["exercises"] if e["id"] == row["id"])
    assert swapped["exercise_id"] == pick and swapped["replaced_exercise_id"] == row["exercise_id"]
    # the swap is remembered: the next generation prefers the chosen exercise
    nxt = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    assert pick in {e["exercise_id"] for e in nxt["exercises"]}


def run_session(client: TestClient, unit: str = "kg") -> dict:
    w = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    started = client.post(f"/api/training/workouts/{w['id']}/start").json()
    assert started["status"] == "in_progress" and started["started_at"].endswith("Z")
    first = started["exercises"][0]
    for reps in (10, 10, 9):
        client.post(f"/api/training/workouts/{w['id']}/sets",
                    json={"workout_exercise_id": first["id"], "reps": reps, "weight": 60 if unit == "kg" else 135, "unit": unit})
    return client.get(f"/api/training/workouts/{w['id']}").json()


def test_start_log_sets_and_finish(client, app):
    setup_user(client, "log")
    w = run_session(client)
    first = w["exercises"][0]
    assert [s["reps"] for s in first["sets"]] == [10, 10, 9] and first["completed"] is True
    assert first["sets"][0]["weight_kg"] == 60 and first["sets"][0]["weight_lb"] == 132.3
    # pretend the session started 70 minutes ago, then finish it
    with app.state.session_factory() as db:
        db.execute(update(Workout).where(Workout.id == w["id"]).values(started_at=datetime.now(UTC) - timedelta(minutes=70)))
        db.commit()
    done = client.post(f"/api/training/workouts/{w['id']}/finish").json()
    s = done["summary"]
    assert done["status"] == "completed"
    assert s["actual_minutes"] == 70 and s["difference_minutes"] == 70 - s["planned_minutes"]
    assert s["sets_logged"] == 3 and s["volume_kg"] == 60 * 29
    hist = client.get("/api/training/summary").json()
    assert hist["history"][0]["id"] == w["id"] and hist["completed_last_7_days"] == 1
    assert hist["average_difference_minutes"] == s["difference_minutes"]
    # logging after completion is refused
    assert client.post(f"/api/training/workouts/{w['id']}/sets",
                       json={"workout_exercise_id": first["id"], "reps": 5}).status_code == 409


def test_pound_entries_are_stored_in_kg(client):
    setup_user(client, "lbs")
    w = run_session(client, unit="lb")
    s = w["exercises"][0]["sets"][0]
    assert s["weight_kg"] == round(135 * 0.45359237, 2) == 61.23 and s["weight_lb"] == 135.0


def test_set_validation(client):
    setup_user(client, "val")
    w = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    ex = w["exercises"][0]
    assert client.post(f"/api/training/workouts/{w['id']}/sets", json={"workout_exercise_id": ex["id"], "reps": 5}).status_code == 409  # not started
    client.post(f"/api/training/workouts/{w['id']}/start")
    url = f"/api/training/workouts/{w['id']}/sets"
    assert client.post(url, json={"workout_exercise_id": ex["id"], "reps": -1}).status_code == 422
    assert client.post(url, json={"workout_exercise_id": ex["id"], "reps": 5, "weight": 900}).status_code == 422
    assert client.post(url, json={"workout_exercise_id": ex["id"]}).status_code == 422  # reps required
    assert client.post(url, json={"workout_exercise_id": 99999, "reps": 5}).status_code == 404
    assert client.post(f"/api/training/workouts/{w['id']}/finish").status_code == 422  # nothing logged
    r = client.post(url, json={"workout_exercise_id": ex["id"], "reps": 8, "weight": 50}).json()
    set_id = r["exercises"][0]["sets"][0]["id"]
    edited = client.patch(f"/api/training/workouts/{w['id']}/sets/{set_id}", json={"reps": 9}).json()
    assert edited["exercises"][0]["sets"][0]["reps"] == 9
    assert client.delete(f"/api/training/workouts/{w['id']}/sets/{set_id}").json()["exercises"][0]["sets"] == []


def test_progression_suggests_weight_from_history(client, app):
    setup_user(client, "prg")
    w = run_session(client)
    client.post(f"/api/training/workouts/{w['id']}/finish")
    nxt_lower = client.post("/api/training/generate", json={"day_type": "upper"}).json()
    first_id = w["exercises"][0]["exercise_id"]
    again = next((e for e in nxt_lower["exercises"] if e["exercise_id"] == first_id), None)
    assert again is not None and again["suggested_weight_kg"] == 60 and "Last time: 60 kg" in again["last_summary"]


def test_workouts_are_isolated_between_users(two_users):
    alice, bob = two_users
    for c in (alice, bob):
        assert c.put("/api/profile", json=TRAINING_PROFILE).status_code == 200
    w = alice.post("/api/training/generate", json={"day_type": "upper"}).json()
    ex = w["exercises"][0]
    base = f"/api/training/workouts/{w['id']}"
    assert bob.get(base).status_code == 404
    assert bob.post(f"{base}/start").status_code == 404
    assert bob.get(f"{base}/exercises/{ex['id']}/alternatives").status_code == 404
    assert bob.post(f"{base}/exercises/{ex['id']}/replace", json={"exercise_id": "Pushups"}).status_code == 404
    assert bob.delete(base).status_code == 404
    alice.post(f"{base}/start")
    assert bob.post(f"{base}/sets", json={"workout_exercise_id": ex["id"], "reps": 5}).status_code == 404
    assert bob.post(f"{base}/finish").status_code == 404
    assert bob.get("/api/training/workouts").json()["workouts"] == []
    assert bob.get("/api/training/summary").json()["in_progress"] is None


def test_history_survives_restart(db_url, tmp_path):
    from app.main import create_app

    with TestClient(create_app(database_url=db_url, frontend_dist=tmp_path / "x")) as c:
        setup_user(c, "rst")
        w = run_session(c)
        c.post(f"/api/training/workouts/{w['id']}/finish")
    with TestClient(create_app(database_url=db_url, frontend_dist=tmp_path / "x")) as c2:
        c2.post("/api/auth/login", json={"username": "rst", "password": "correct-horse-1"})
        hist = c2.get("/api/training/summary").json()["history"]
        assert len(hist) == 1 and hist[0]["status"] == "completed" and hist[0]["summary"]["sets_logged"] == 3


def test_demo_training_is_flagged(client, app):
    from app.seed import ensure_demo_training, ensure_demo_user

    with app.state.session_factory() as db:
        ensure_demo_user(db)
        assert ensure_demo_training(db) == 2 and ensure_demo_training(db) == 0
    client.post("/api/auth/login", json={"username": "demo", "password": "venn-demo-2026"})
    hist = client.get("/api/training/summary").json()["history"]
    assert len(hist) == 2 and all(h["is_demo"] for h in hist)


def test_check_exercise_reasons_are_specific():
    c = ctx(equipment=frozenset({"dumbbell"}), limitations=(Limitation("knee", "caution"),))
    r = check_exercise(catalog()["Barbell_Squat"], c)
    assert not r.ok and any("barbell" in x for x in r.reasons) and any("knee heavily" in x for x in r.reasons)
