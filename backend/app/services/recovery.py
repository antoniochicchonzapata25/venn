"""Estimated muscle recovery from logged workouts (deterministic, no AI).

This is an illustrative heuristic, not a validated physiological model. It does not measure soreness,
injury or readiness; it only summarises how much logged work recently targeted each muscle group.

Model
-----
1. Each catalog exercise maps to muscle groups through its free-exercise-db muscles:
   a primary muscle counts 1.0 per logged set, a secondary muscle 0.5 (never full intensity).
   Several catalog muscles can map to one group (lats, middle back, traps -> back); the group takes the
   highest weight, so one exercise is never counted twice for the same group. Calves, forearms and the
   cardiovascular system are not among the ten groups and are ignored.
2. Only sets actually logged in completed workouts count (reps > 0 or a duration). Planned sets do not.
3. Residual load for a group = sum over completed workouts in the last 7 days of
   weighted sets x max(0, 1 - hours since the workout finished / 72).
4. Category: no weighted sets in the last 7 days -> "none" (not assessed, grey);
   residual < 2 -> "low"; 2 to < 5 -> "moderate"; >= 5 -> "high".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.services.exercises import catalog

GROUPS: dict[str, str] = {
    "back": "Back", "biceps": "Biceps", "chest": "Chest", "shoulders": "Shoulders", "triceps": "Triceps",
    "lower_back": "Lower back", "abs": "Abs", "glutes": "Glutes", "hamstrings": "Hamstrings", "quadriceps": "Quadriceps",
}

# free-exercise-db muscle name -> Venn muscle group
CATALOG_MUSCLE_TO_GROUP: dict[str, str] = {
    "lats": "back", "middle back": "back", "traps": "back", "lower back": "lower_back", "abdominals": "abs",
    "chest": "chest", "shoulders": "shoulders", "biceps": "biceps", "triceps": "triceps", "glutes": "glutes",
    "hamstrings": "hamstrings", "quadriceps": "quadriceps",
}
IGNORED_MUSCLES = {"calves", "forearms", "cardiovascular system"}

PRIMARY_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.5
WINDOW_DAYS = 7
DECAY_HOURS = 72.0
MODERATE_AT = 2.0  # residual weighted sets
HIGH_AT = 5.0

STATE_LABELS = {
    "none": "Not assessed (no logged sets in the last 7 days)",
    "low": "Low estimated fatigue",
    "moderate": "Moderate estimated fatigue",
    "high": "High estimated fatigue",
}

DISCLAIMER = ("An estimate from your logged workouts using illustrative thresholds, not a medically validated "
              "recovery rule. Real recovery varies between people (sleep, nutrition, stress, training age). "
              "It does not measure soreness or injury or tell you whether it is safe to train.")


def exercise_groups(exercise_id: str) -> dict[str, float]:
    """Muscle group -> weight per set for one catalog exercise (empty if the exercise is unknown)."""
    ex = catalog().get(exercise_id)
    if ex is None:
        return {}
    out: dict[str, float] = {}
    for muscles, weight in ((ex.secondary_muscles, SECONDARY_WEIGHT), (ex.primary_muscles, PRIMARY_WEIGHT)):
        for m in muscles:
            group = CATALOG_MUSCLE_TO_GROUP.get(m)
            if group:
                out[group] = max(out.get(group, 0.0), weight)
    return out


@dataclass
class LoggedExercise:
    exercise_id: str
    name: str
    sets: int  # logged sets with reps > 0 or a duration


@dataclass
class CompletedWorkout:
    id: int
    name: str
    finished_at: datetime
    is_demo: bool
    exercises: list[LoggedExercise] = field(default_factory=list)


def classify(residual: float, weighted_sets_in_window: float) -> str:
    if weighted_sets_in_window <= 0:
        return "none"
    if residual >= HIGH_AT:
        return "high"
    if residual >= MODERATE_AT:
        return "moderate"
    return "low"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def local_date(dt: datetime, tz_offset_minutes: int | None) -> date:
    """Browser-local calendar date (tz_offset = Date.getTimezoneOffset(), minutes behind UTC)."""
    return (_aware(dt) - timedelta(minutes=tz_offset_minutes or 0)).date()


def estimate(workouts: list[CompletedWorkout], now: datetime, tz_offset_minutes: int | None = None) -> dict:
    now = _aware(now)
    workouts = sorted(workouts, key=lambda w: _aware(w.finished_at), reverse=True)
    window_start = now - timedelta(days=WINDOW_DAYS)

    groups: dict[str, dict] = {
        g: {"id": g, "label": label, "residual": 0.0, "weighted_sets_7d": 0.0, "last_workout": None, "exercises": []}
        for g, label in GROUPS.items()
    }
    for w in workouts:
        finished = _aware(w.finished_at)
        if finished > now:
            continue
        hours = (now - finished).total_seconds() / 3600
        decay = max(0.0, 1.0 - hours / DECAY_HOURS)
        per_group: dict[str, list[dict]] = {}
        for e in w.exercises:
            if e.sets <= 0:
                continue
            for g, weight in exercise_groups(e.exercise_id).items():
                per_group.setdefault(g, []).append(
                    {"name": e.name, "sets": e.sets, "role": "primary" if weight == PRIMARY_WEIGHT else "secondary",
                     "weighted_sets": round(e.sets * weight, 1)})
        for g, items in per_group.items():
            weighted = sum(i["weighted_sets"] for i in items)
            info = groups[g]
            if info["last_workout"] is None:  # workouts are newest first
                info["last_workout"] = {"id": w.id, "name": w.name, "finished_at": finished.isoformat(),
                                        "hours_ago": round(hours, 1), "is_demo": w.is_demo,
                                        "local_date": local_date(finished, tz_offset_minutes).isoformat()}
                info["exercises"] = items
            if finished >= window_start:
                info["weighted_sets_7d"] += weighted
                info["residual"] += weighted * decay

    for info in groups.values():
        info["residual"] = round(info["residual"], 1)
        info["weighted_sets_7d"] = round(info["weighted_sets_7d"], 1)
        info["state"] = classify(info["residual"], info["weighted_sets_7d"])
        info["state_label"] = STATE_LABELS[info["state"]]

    last = next((w for w in workouts if _aware(w.finished_at) <= now), None)
    last_out = None
    if last is not None:
        trained = {g for e in last.exercises if e.sets > 0 for g in exercise_groups(e.exercise_id)}
        finished = _aware(last.finished_at)
        last_out = {
            "id": last.id, "name": last.name, "finished_at": finished.isoformat(), "is_demo": last.is_demo,
            "local_date": local_date(finished, tz_offset_minutes).isoformat(),
            "days_since": (local_date(now, tz_offset_minutes) - local_date(finished, tz_offset_minutes)).days,
            "groups_trained": len(trained),
        }
    counts = {s: sum(1 for i in groups.values() if i["state"] == s) for s in ("low", "moderate", "high", "none")}
    return {
        "has_history": last is not None,
        "last_workout": last_out,
        "counts": counts,
        "groups": list(groups.values()),
        "model": {
            "window_days": WINDOW_DAYS, "decay_hours": DECAY_HOURS, "moderate_at": MODERATE_AT, "high_at": HIGH_AT,
            "primary_weight": PRIMARY_WEIGHT, "secondary_weight": SECONDARY_WEIGHT,
            "explanation": (f"Each logged set counts 1.0 for an exercise's primary muscle group and 0.5 for a secondary one. "
                            f"Sets from completed workouts in the last {WINDOW_DAYS} days fade linearly to zero over "
                            f"{DECAY_HOURS:.0f} hours. Remaining load below {MODERATE_AT:g} weighted sets = low, "
                            f"{MODERATE_AT:g} to under {HIGH_AT:g} = moderate, {HIGH_AT:g} or more = high. Groups with no "
                            f"logged sets in {WINDOW_DAYS} days are not assessed."),
            "disclaimer": DISCLAIMER,
            "states": STATE_LABELS,
        },
    }
