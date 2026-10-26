"""Milestone 3.5: goal details, target weight/date projection, units, training goals and cardio."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.goal_projection import PACE_RATES, projection
from app.services.workout_generator import History, generate
from app.services.workout_rules import TrainingContext
from tests.conftest import VALID_PROFILE, register

FUTURE = (date.today() + timedelta(days=120)).isoformat()


def test_old_profile_payload_still_works(client):
    register(client, "old")
    r = client.put("/api/profile", json={**VALID_PROFILE, "units": "imperial"})
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["weight_unit"] == "lb" and p["units"] == "imperial" and p["height_unit"] == "cm"
    assert p["target_weight_kg"] is None and p["cardio_in_plan"] is False


def test_per_field_units_are_display_only(client):
    register(client, "uni")
    r = client.put("/api/profile", json={**VALID_PROFILE, "height_unit": "ft_in", "weight_unit": "lb"}).json()
    assert r["profile"]["height_cm"] == 165 and r["profile"]["weight_kg"] == 60  # stored metric
    assert r["profile"]["units"] == "imperial"
    # targets are identical whatever the display units
    t1 = r["target"]["kcal"]
    t2 = client.put("/api/profile", json={**VALID_PROFILE, "height_unit": "cm", "weight_unit": "kg"}).json()["target"]["kcal"]
    assert t1 == t2


def test_target_weight_rules(client):
    register(client, "twt")
    lose = {**VALID_PROFILE, "goal": "lose", "goal_rate_pct": 0.5, "goal_focus": "fat_loss"}
    assert client.put("/api/profile", json={**lose, "target_weight_kg": 65}).status_code == 422  # above current 60
    assert client.put("/api/profile", json={**lose, "target_date": FUTURE}).status_code == 422  # date without target
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.put("/api/profile", json={**lose, "target_weight_kg": 57, "target_date": past}).status_code == 422
    ok = client.put("/api/profile", json={**lose, "target_weight_kg": 57, "target_date": FUTURE}).json()["profile"]
    proj = ok["goal_projection"]
    # 0.5% of 60 kg = 0.3 kg/week; 3 kg -> 10 weeks
    assert proj["weekly_change_kg"] == 0.3 and proj["weeks_at_pace"] == 10
    assert "within Venn's limit" in proj["date_check"]
    # maintain clears any target weight: no forced scale goal
    m = client.put("/api/profile", json={**VALID_PROFILE, "goal": "maintain", "goal_focus": "recomp",
                                         "target_weight_kg": 50}).json()["profile"]
    assert m["target_weight_kg"] is None and m["goal_focus"] == "recomp" and m["goal_projection"] is None


def test_projection_flags_unrealistic_dates():
    soon = date.today() + timedelta(weeks=4)
    p = projection("lose", 100, 0.5, 80, soon)  # 20 kg in 4 weeks = 5% per week
    assert p["required_rate_pct"] == 5.0 and "above Venn's maximum of 1.0%" in p["date_check"]
    assert projection("maintain", 80, 0, 70, None) is None
    assert all(r <= {"lose": 1.0, "gain": 0.5}[g] for g, rates in PACE_RATES.items() for r in rates.values())


def test_optional_fields_validation(client):
    register(client, "opt")
    assert client.put("/api/profile", json={**VALID_PROFILE, "body_fat_pct": 1}).status_code == 422
    assert client.put("/api/profile", json={**VALID_PROFILE, "body_fat_pct": 22.5}).json()["profile"]["body_fat_pct"] == 22.5
    assert client.put("/api/profile", json={**VALID_PROFILE, "cardio_sessions_per_week": 2, "cardio_in_plan": True}).status_code == 422
    p = client.put("/api/profile", json={**VALID_PROFILE, "training_goal": "muscular_endurance",
                                         "secondary_training_goal": "muscular_endurance"}).json()["profile"]
    assert p["secondary_training_goal"] is None  # same as primary -> dropped
    assert client.put("/api/profile", json={**VALID_PROFILE, "height_unit": "furlongs"}).status_code == 422


def ctx(**kw) -> TrainingContext:
    base = dict(equipment=frozenset({"dumbbell", "bench", "cable", "machine", "barbell"}), limitations=(),
                experience="intermediate", goal="build_muscle", budget_minutes=60)
    return TrainingContext(**{**base, **kw})


def test_new_training_goals_generate_valid_plans():
    for goal in ("muscular_endurance", "cardio_fitness"):
        plan = generate(ctx=ctx(goal=goal), preferred_split="full_body", days_per_week=3, history=History())
        assert plan.est_seconds <= 60 * 60 and plan.items


def test_cardio_block_fits_inside_the_budget():
    plan = generate(ctx=ctx(cardio_minutes=20), preferred_split="upper_lower", days_per_week=4,
                    history=History(), day_type="upper")
    cardio = plan.items[-1]
    assert cardio.exercise.id == "Cardio_Session" and cardio.target_seconds == 20 * 60
    assert plan.est_seconds <= 60 * 60
    assert any("cardio block" in line for line in plan.explanation)
    short = generate(ctx=ctx(cardio_minutes=30, budget_minutes=30), preferred_split="full_body", days_per_week=3,
                     history=History())
    assert short.est_seconds <= 30 * 60
    assert all(i.exercise.id != "Cardio_Session" for i in short.items)
    assert any("too short to add a cardio block" in line for line in short.explanation)


def test_training_options_and_split_change(client):
    register(client, "spl")
    client.put("/api/profile", json={**VALID_PROFILE, "days_per_week": 4, "equipment": ["dumbbell", "bench"],
                                     "cardio_sessions_per_week": 2, "cardio_minutes": 15, "cardio_in_plan": True})
    opts = client.get("/api/training/options").json()
    assert opts["split"] == "full_body" or opts["split"] == "upper_lower"
    w = client.post("/api/training/generate", json={"split": "push_pull_legs", "day_type": "upper"}).json()
    assert w["split"] == "push_pull_legs" and w["day_type"] in ("push", "pull", "legs")
    assert client.get("/api/profile").json()["preferred_split"] == "push_pull_legs"  # saved as default
    assert w["exercises"][-1]["exercise_id"] == "Cardio_Session"
    assert w["planned_minutes"] <= w["budget_minutes"]
