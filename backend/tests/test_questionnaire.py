"""Milestone 3.6: protein reference weight and range, cardio schedule, eating pattern, exercise ability."""

from __future__ import annotations

import pytest

from app.services.targets import TargetInputs, calculate_targets, protein_range, protein_status
from app.services.workout_generator import History, generate
from app.services.workout_rules import TrainingContext
from tests.conftest import VALID_PROFILE, register


# --- protein reference weight ---------------------------------------------------------------

def test_protein_uses_current_weight_by_default():
    # 80 kg x 2.0 = 160 g (well under 35% of ~2,600 kcal)
    r = calculate_targets(TargetInputs("male", 30, 180, 80, "moderate", "maintain", protein_level="high"))
    assert r.protein_reference == "current weight" and r.protein_unrounded == 160 and r.protein_g == 160


def test_protein_uses_target_weight_when_losing_scale_weight():
    # 110 kg, losing toward 90 kg: 90 x 2.0 = 180 g instead of 220 g
    r = calculate_targets(TargetInputs("male", 35, 180, 110, "moderate", "lose", 0.5, "high", target_weight_kg=90))
    assert r.protein_reference == "target weight" and r.protein_reference_kg == 90 and r.protein_g == 180


@pytest.mark.parametrize("goal, rate, target", [("lose", 0.5, None), ("maintain", 0, 70), ("gain", 0.25, 95)])
def test_protein_falls_back_to_current_weight(goal, rate, target):
    r = calculate_targets(TargetInputs("female", 30, 170, 80, "light", goal, rate, "standard", target_weight_kg=target))
    assert r.protein_reference == "current weight" and r.protein_unrounded == pytest.approx(128.0)  # 80 x 1.6


def test_protein_cap_still_applies_to_reference():
    # 60 kg x 2.2 = 132 g = 528 kcal > 35% of 1,350 kcal -> capped at 118.1 g
    r = calculate_targets(TargetInputs("female", 25, 165, 60, "sedentary", "lose", 0.5, "very_high"))
    assert r.protein_capped and r.protein_g == 118


# --- protein tolerance range ------------------------------------------------------------------

def test_range_is_plus_minus_5_percent_of_unrounded_target():
    assert protein_range(180) == (171, 189)
    assert protein_range(118.125) == (112, 124)   # 112.22 -> 112 ; 124.03 -> 124
    assert protein_range(170) == (162, 179)       # 161.5 -> 162 (half up) ; 178.5 -> 179


@pytest.mark.parametrize("eaten, state, to_low, above", [
    (0, "below", 171, 0), (170.4, "below", 1, 0), (170.5, "within", 0, 0),   # 170.5 rounds to 171
    (180, "within", 0, 0), (189.4, "within", 0, 0), (189.5, "above", 0, 1), (200, "above", 0, 11),
])
def test_range_status_boundaries(eaten, state, to_low, above):
    s = protein_status(eaten, 180)
    assert (s["state"], s["to_low"], s["above_high"]) == (state, to_low, above)
    assert (s["low"], s["high"], s["nominal"]) == (171, 189, 180)


def test_no_target_means_no_range():
    assert protein_status(50, None) is None


def test_day_summary_reports_protein_range(client):
    register(client, "prr")
    client.put("/api/profile", json=VALID_PROFILE)  # female 60 kg, standard -> 96 g
    day = client.get("/api/nutrition/day", params={"date": "2026-10-26", "tz_offset": 0}).json()
    if day["target"] is None:  # the target is created "now"; ask for today in server-local time instead
        from datetime import date
        day = client.get("/api/nutrition/day", params={"date": date.today().isoformat()}).json()
    pr = day["protein_range"]
    assert pr["nominal"] == 96 and (pr["low"], pr["high"]) == (91, 101) and pr["state"] == "below" and pr["to_low"] == 91
    # units are display-only: the same profile in lb gives the same protein target
    lb = client.put("/api/profile", json={**VALID_PROFILE, "weight_unit": "lb"}).json()["target"]
    assert lb["protein_g"] == 96


# --- profile fields ---------------------------------------------------------------------------------

def test_cardio_schedule_is_independent_of_strength_days(client):
    register(client, "crd")
    base = {**VALID_PROFILE, "days_per_week": 3}
    p = client.put("/api/profile", json={**base, "cardio_schedule": "separate_days", "cardio_sessions_per_week": 4,
                                         "cardio_minutes": 30}).json()["profile"]
    assert (p["days_per_week"], p["cardio_sessions_per_week"], p["cardio_in_plan"]) == (3, 4, False)
    p = client.put("/api/profile", json={**base, "cardio_schedule": "strength_days", "cardio_sessions_per_week": 3,
                                         "cardio_minutes": 15}).json()["profile"]
    assert p["cardio_in_plan"] is True
    p = client.put("/api/profile", json={**base, "cardio_schedule": "none", "cardio_sessions_per_week": 5,
                                         "cardio_minutes": 20}).json()["profile"]
    assert (p["cardio_sessions_per_week"], p["cardio_in_plan"]) == (0, False)
    assert client.put("/api/profile", json={**base, "cardio_schedule": "mix", "cardio_sessions_per_week": 0}).status_code == 422
    opts = client.get("/api/training/options").json()["weekly_plan"]
    assert opts["strength_days"] == 3 and opts["cardio_schedule"] == "none"


def test_eating_pattern_and_other_text(client):
    register(client, "eat")
    p = client.put("/api/profile", json={**VALID_PROFILE, "eating_pattern": "none", "dietary_preferences": []}).json()["profile"]
    assert p["eating_pattern"] == "none"
    p = client.put("/api/profile", json={**VALID_PROFILE, "eating_pattern": "other",
                                         "eating_pattern_other": "  Low-FODMAP\x07 "}).json()["profile"]
    assert p["eating_pattern_other"] == "Low-FODMAP"
    p = client.put("/api/profile", json={**VALID_PROFILE, "eating_pattern": "vegan", "eating_pattern_other": "x"}).json()["profile"]
    assert p["eating_pattern_other"] is None
    assert client.put("/api/profile", json={**VALID_PROFILE, "eating_pattern": "keto"}).status_code == 422


def test_gym_location_does_not_restrict_equipment(client):
    register(client, "gym")
    p = client.put("/api/profile", json={**VALID_PROFILE, "gym_location": "bodyweight",
                                         "equipment": ["dumbbell", "bands"]}).json()["profile"]
    assert p["gym_location"] == "bodyweight" and p["equipment"] == ["dumbbell", "bands"]  # selection wins


def test_exercise_ability_is_saved_and_validated(client):
    register(client, "abl")
    ability = {"pushups": "5_9", "pullups": "none", "dips": "unsure"}
    p = client.put("/api/profile", json={**VALID_PROFILE, "exercise_ability": ability}).json()["profile"]
    assert p["exercise_ability"] == ability
    assert client.get("/api/profile").json()["exercise_ability"] == ability
    assert client.put("/api/profile", json={**VALID_PROFILE, "exercise_ability": {"squats": "5_9"}}).status_code == 422
    assert client.put("/api/profile", json={**VALID_PROFILE, "exercise_ability": {"pushups": "max"}}).status_code == 422


def test_cannot_do_yet_removes_bodyweight_moves_from_generation():
    ctx = TrainingContext(equipment=frozenset({"pull-up bar"}), limitations=(), experience="intermediate",
                          goal="general_fitness", budget_minutes=60,
                          cannot_do_yet=frozenset({"Pullups", "Chin-Up", "Pushups"}))
    plan = generate(ctx=ctx, preferred_split="full_body", days_per_week=3, history=History())
    ids = {i.exercise.id for i in plan.items}
    assert not ids & {"Pullups", "Chin-Up", "Pushups"}
    assert plan.est_seconds <= 60 * 60


@pytest.mark.parametrize("minutes", [30, 45, 60, 75, 90, 105, 120, 135, 150, 180])
def test_range_upper_bounds_are_respected(minutes):
    ctx = TrainingContext(equipment=frozenset({"barbell", "dumbbell", "bench", "cable", "machine"}), limitations=(),
                          experience="advanced", goal="get_stronger", budget_minutes=minutes)
    plan = generate(ctx=ctx, preferred_split="upper_lower", days_per_week=4, history=History(), day_type="lower")
    assert plan.est_seconds <= minutes * 60
