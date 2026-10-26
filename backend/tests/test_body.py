"""Body tracking (weight, measurements), the deterministic recovery estimate, and user-reported soreness."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models import Workout
from app.services import recovery
from app.services.exercises import catalog
from app.services.recovery import CompletedWorkout, LoggedExercise, classify, estimate, exercise_groups
from tests.conftest import register
from tests.test_training import TRAINING_PROFILE, run_session, setup_user

TODAY = date.today().isoformat()
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# --- weight ---------------------------------------------------------------------------------

def test_weight_empty_state(client):
    register(client, "body_w0")
    r = client.get("/api/body/weights").json()
    assert r["entries"] == [] and r["latest"] is None and r["previous"] is None and r["change_kg"] is None


def test_weight_create_compare_replace_and_delete(client):
    register(client, "body_w1")
    assert client.post("/api/body/weights", json={"entry_date": days_ago(7), "weight": 82.4}).status_code == 201
    r = client.post("/api/body/weights", json={"entry_date": days_ago(0), "weight": 180, "unit": "lb"}).json()
    assert r["latest"]["weight_kg"] == pytest.approx(81.65, abs=0.01)  # 180 lb stored as kg
    assert r["previous"]["weight_kg"] == 82.4
    assert r["change_kg"] == pytest.approx(-0.75, abs=0.01) and r["days_between"] == 7
    # same date again replaces the value instead of creating a duplicate
    r = client.post("/api/body/weights", json={"entry_date": days_ago(0), "weight": 81.0}).json()
    assert r["replaced"] is True and len(r["entries"]) == 2 and r["latest"]["weight_kg"] == 81.0
    # out-of-order entry: latest/previous follow the dates, not insertion order
    r = client.post("/api/body/weights", json={"entry_date": days_ago(3), "weight": 81.8}).json()
    assert [e["entry_date"] for e in r["entries"]] == [days_ago(0), days_ago(3), days_ago(7)]
    assert r["previous"]["weight_kg"] == 81.8 and r["change_kg"] == pytest.approx(-0.8)
    assert client.delete(f"/api/body/weights/{r['latest']['id']}").status_code == 204
    after = client.get("/api/body/weights").json()
    assert after["latest"]["weight_kg"] == 81.8 and len(after["entries"]) == 2


@pytest.mark.parametrize("payload, fragment", [
    ({"weight": 12}, "implausible"),
    ({"weight": 900, "unit": "lb"}, "implausible"),
    ({"weight": -5}, "greater than 0"),
    ({"weight": 80, "unit": "stone"}, "pattern"),
    ({"weight": 80, "entry_date": "2099-01-01"}, "future"),
    ({"weight": 80, "entry_date": "1990-05-01"}, "2000-01-01"),
    ({"weight": 80, "entry_date": "not-a-date"}, "date"),
    ({"weight": 80, "user_id": 2}, "Extra inputs"),
])
def test_weight_validation(client, payload, fragment):
    register(client, "body_wv")
    body = {"entry_date": TODAY, **payload}
    r = client.post("/api/body/weights", json=body)
    assert r.status_code == 422
    assert fragment.lower() in r.text.lower()
    assert client.get("/api/body/weights").json()["entries"] == []


def test_weight_lb_message_uses_lb(client):
    register(client, "wlb")
    r = client.post("/api/body/weights", json={"entry_date": TODAY, "weight": 30, "unit": "lb"})
    assert r.status_code == 422 and "lb" in r.json()["detail"][0] and "55-772 lb" in r.json()["detail"][0]


# --- measurements -----------------------------------------------------------------------------

def test_measurements_empty_state(client):
    register(client, "body_m0")
    r = client.get("/api/body/measurements").json()
    assert r["entries"] == [] and all(c["latest_cm"] is None and c["change_cm"] is None for c in r["comparison"].values())
    assert r["fields"] == ["waist", "chest", "hips", "biceps", "thigh"]


def test_measurements_missing_values_and_per_field_comparison(client):
    register(client, "body_m1")
    client.post("/api/body/measurements", json={"entry_date": days_ago(14), "waist": 90, "chest": 104, "hips": 100})
    client.post("/api/body/measurements", json={"entry_date": days_ago(7), "waist": 89, "biceps": 36})  # chest/hips not measured
    r = client.post("/api/body/measurements", json={"entry_date": TODAY, "unit": "in", "waist": 34.5}).json()
    assert len(r["entries"]) == 3
    latest = r["entries"][0]
    assert latest["waist_cm"] == pytest.approx(87.6, abs=0.05) and latest["chest_cm"] is None
    c = r["comparison"]
    assert c["waist"]["previous_cm"] == 89 and c["waist"]["change_cm"] == pytest.approx(-1.4, abs=0.05)
    # chest only recorded once: latest from 14 days ago, nothing to compare
    assert c["chest"]["latest_cm"] == 104 and c["chest"]["latest_date"] == days_ago(14) and c["chest"]["change_cm"] is None
    assert c["biceps"]["latest_cm"] == 36 and c["thigh"]["latest_cm"] is None
    # delete the oldest: chest disappears entirely
    oldest = r["entries"][-1]["id"]
    assert client.delete(f"/api/body/measurements/{oldest}").status_code == 204
    assert client.get("/api/body/measurements").json()["comparison"]["chest"]["latest_cm"] is None


def test_measurement_same_date_replaces(client):
    register(client, "body_m2")
    client.post("/api/body/measurements", json={"entry_date": TODAY, "waist": 90, "hips": 100})
    r = client.post("/api/body/measurements", json={"entry_date": TODAY, "waist": 88}).json()
    assert r["replaced"] is True and len(r["entries"]) == 1
    assert r["entries"][0]["waist_cm"] == 88 and r["entries"][0]["hips_cm"] is None


@pytest.mark.parametrize("payload, fragment", [
    ({}, "at least one"),
    ({"waist": 10}, "Waist"),
    ({"biceps": 200}, "Biceps"),
    ({"unit": "in", "thigh": 70}, "in)"),
    ({"unit": "mm", "waist": 800}, "pattern"),
    ({"waist": 0}, "greater than 0"),
    ({"neck": 40}, "Extra inputs"),
])
def test_measurement_validation(client, payload, fragment):
    register(client, "body_mv")
    r = client.post("/api/body/measurements", json={"entry_date": TODAY, **payload})
    assert r.status_code == 422 and fragment.lower() in r.text.lower()
    assert client.get("/api/body/measurements").json()["entries"] == []


def test_body_requires_login(client):
    for path in ("/api/body/weights", "/api/body/measurements", "/api/body/recovery"):
        assert client.get(path).status_code == 401


def test_cross_user_access_is_denied(two_users):
    alice, bob = two_users
    w = alice.post("/api/body/weights", json={"entry_date": TODAY, "weight": 70}).json()["latest"]
    m = alice.post("/api/body/measurements", json={"entry_date": TODAY, "waist": 80}).json()["entries"][0]
    alice.put("/api/body/soreness/chest", json={"rating": 6})
    # bob sees nothing of alice's and cannot delete her rows by id
    assert bob.get("/api/body/weights").json()["entries"] == []
    assert bob.get("/api/body/measurements").json()["entries"] == []
    assert bob.get("/api/body/recovery").json()["soreness"] == {}
    assert bob.delete(f"/api/body/weights/{w['id']}").status_code == 404
    assert bob.delete(f"/api/body/measurements/{m['id']}").status_code == 404
    assert bob.delete("/api/body/soreness/chest").status_code == 404
    # bob writing the same date creates his own row; alice's value is untouched
    bob.post("/api/body/weights", json={"entry_date": TODAY, "weight": 90})
    assert alice.get("/api/body/weights").json()["latest"]["weight_kg"] == 70
    assert alice.get("/api/body/recovery").json()["soreness"]["chest"]["rating"] == 6


# --- muscle-group mapping ---------------------------------------------------------------------

def test_mapping_weights_primary_full_and_secondary_half():
    assert exercise_groups("Barbell_Squat") == {"quadriceps": 1.0, "glutes": 0.5, "hamstrings": 0.5, "lower_back": 0.5}
    assert exercise_groups("Romanian_Deadlift") == {"hamstrings": 1.0, "glutes": 0.5, "lower_back": 0.5}
    # lats (secondary) and middle back (primary) both map to back: counted once, at the primary weight
    assert exercise_groups("Seated_Cable_Rows") == {"back": 1.0, "biceps": 0.5, "shoulders": 0.5}
    assert exercise_groups("Plank") == {"abs": 1.0}
    assert exercise_groups("Cardio_Session") == {}  # cardiovascular system is not a muscle group
    assert exercise_groups("Not_A_Real_Exercise") == {}


def test_every_catalog_muscle_is_mapped_or_explicitly_ignored():
    for ex in catalog().values():
        for m in (*ex.primary_muscles, *ex.secondary_muscles):
            assert m in recovery.CATALOG_MUSCLE_TO_GROUP or m in recovery.IGNORED_MUSCLES, (ex.id, m)
        if ex.pattern != "cardio" and ex.primary_muscles != ("calves",):
            assert any(w == 1.0 for w in exercise_groups(ex.id).values()), ex.id  # every lift has a primary group


# --- recovery model ---------------------------------------------------------------------------

def wk(hours_ago: float, *exercises: tuple[str, int], wid: int = 1, demo: bool = False) -> CompletedWorkout:
    return CompletedWorkout(id=wid, name=f"W{wid}", finished_at=NOW - timedelta(hours=hours_ago), is_demo=demo,
                            exercises=[LoggedExercise(exercise_id=e, name=e.replace("_", " "), sets=n) for e, n in exercises])


def group(result: dict, gid: str) -> dict:
    return next(g for g in result["groups"] if g["id"] == gid)


def test_no_history_is_not_assessed():
    r = estimate([], NOW)
    assert r["has_history"] is False and r["last_workout"] is None
    assert r["counts"] == {"low": 0, "moderate": 0, "high": 0, "none": 10}
    assert all(g["state"] == "none" and g["last_workout"] is None for g in r["groups"])


@pytest.mark.parametrize("residual, sets, state", [
    (0, 0, "none"), (0, 3, "low"), (1.99, 3, "low"), (2.0, 3, "moderate"), (4.99, 6, "moderate"), (5.0, 6, "high"),
])
def test_classification_boundaries(residual, sets, state):
    assert classify(residual, sets) == state


def test_decay_over_time_and_window():
    # 6 primary chest sets: just finished -> high; 36 h -> 3.0 moderate; 60 h -> 1.0 low; 72 h+ -> low (0 residual)
    for hours, state, residual in ((0, "high", 6.0), (36, "moderate", 3.0), (60, "low", 1.0), (100, "low", 0.0)):
        g = group(estimate([wk(hours, ("Barbell_Bench_Press_-_Medium_Grip", 6))], NOW), "chest")
        assert g["state"] == state and g["residual"] == residual, hours
    # older than the 7-day window: not assessed, but the detail still shows the last workout that hit it
    g = group(estimate([wk(24 * 8, ("Barbell_Bench_Press_-_Medium_Grip", 6))], NOW), "chest")
    assert g["state"] == "none" and g["weighted_sets_7d"] == 0 and g["last_workout"]["name"] == "W1"


def test_secondary_muscles_count_half_and_unlogged_sets_do_not_count():
    r = estimate([wk(0, ("Barbell_Squat", 4), ("Plank", 0))], NOW)
    assert group(r, "quadriceps")["residual"] == 4.0 and group(r, "quadriceps")["state"] == "moderate"
    assert group(r, "glutes")["residual"] == 2.0 and group(r, "hamstrings")["exercises"][0]["role"] == "secondary"
    assert group(r, "abs")["state"] == "none"  # plank planned but no set logged
    assert r["last_workout"]["groups_trained"] == 4  # quads, glutes, hamstrings, lower back


def test_multiple_workouts_accumulate_and_counts_are_consistent():
    r = estimate([wk(48, ("Barbell_Bench_Press_-_Medium_Grip", 4), wid=1),
                  wk(10, ("Barbell_Bench_Press_-_Medium_Grip", 3), ("Seated_Cable_Rows", 3), wid=2)], NOW)
    chest = group(r, "chest")
    assert chest["residual"] == pytest.approx(round(4 * (1 - 48 / 72) + 3 * (1 - 10 / 72), 1))
    assert chest["weighted_sets_7d"] == 7 and chest["last_workout"]["id"] == 2
    assert sum(r["counts"].values()) == 10
    assert r["counts"]["none"] == sum(1 for g in r["groups"] if g["state"] == "none")
    assert r["last_workout"]["id"] == 2


def test_days_since_uses_local_calendar_days():
    # finished 23:30 UTC yesterday; at UTC-5 (offset +300) that was 18:30 local yesterday -> 1 day
    w = CompletedWorkout(id=1, name="W", finished_at=datetime(2026, 10, 25, 23, 30, tzinfo=UTC), is_demo=False,
                         exercises=[LoggedExercise("Plank", "Plank", 2)])
    assert estimate([w], NOW, 300)["last_workout"]["days_since"] == 1
    assert estimate([w], NOW, 0)["last_workout"]["local_date"] == "2026-10-25"


def test_recovery_api_uses_only_this_users_logged_workouts(two_users, app):
    alice, bob = two_users
    assert alice.put("/api/profile", json=TRAINING_PROFILE).status_code == 200
    w = run_session(alice)
    with app.state.session_factory() as db:
        db.execute(update(Workout).where(Workout.id == w["id"]).values(started_at=datetime.now(UTC) - timedelta(minutes=40)))
        db.commit()
    alice.post(f"/api/training/workouts/{w['id']}/finish")
    r = alice.get("/api/body/recovery?tz_offset=300").json()
    first = w["exercises"][0]
    assert r["has_history"] is True and r["last_workout"]["id"] == w["id"] and r["last_workout"]["days_since"] == 0
    primary = [g for g, wt in exercise_groups(first["exercise_id"]).items() if wt == 1.0]
    g = group(r, primary[0])
    assert g["state"] == "moderate" and g["exercises"][0]["sets"] == 3  # 3 sets just logged
    assert "not a medically validated" in r["model"]["disclaimer"]
    # bob has no workouts: everything not assessed, nothing invented
    rb = bob.get("/api/body/recovery").json()
    assert rb["has_history"] is False and rb["counts"]["none"] == 10


def test_planned_or_in_progress_workouts_are_ignored(client):
    setup_user(client, "body_ip")
    run_session(client)  # in progress, sets logged, not finished
    r = client.get("/api/body/recovery").json()
    assert r["has_history"] is False and r["counts"]["none"] == 10


# --- user-reported soreness -------------------------------------------------------------------

def test_soreness_set_update_delete_and_validation(client):
    register(client, "body_s1")
    r = client.put("/api/body/soreness/quadriceps", json={"rating": 7}).json()
    assert r["rating"] == 7 and r["recorded_at"]
    r2 = client.put("/api/body/soreness/quadriceps", json={"rating": 3}).json()
    assert r2["rating"] == 3
    rec = client.get("/api/body/recovery").json()
    assert rec["soreness"] == {"quadriceps": {"rating": 3, "recorded_at": r2["recorded_at"]}}
    # the user's rating never changes the workout-based estimate
    assert group(rec, "quadriceps")["state"] == "none"
    assert client.put("/api/body/soreness/quadriceps", json={"rating": 11}).status_code == 422
    assert client.put("/api/body/soreness/neck", json={"rating": 2}).status_code == 404
    assert client.delete("/api/body/soreness/quadriceps").status_code == 204
    assert client.get("/api/body/recovery").json()["soreness"] == {}
