"""Deterministic training rules: compatibility, prescriptions, duration estimates, plan validation.

These are application rules, not model instructions. Every generated routine and every
replacement is checked here before it is shown or saved. Nothing here is medical advice:
the "loads" tags describe where a movement puts load, and they are matched only against
limitations the user reported. Venn never infers a limitation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.exercises import EXPERIENCE_MAX_LEVEL, LEVEL_RANK, PATTERN_LABELS, Exercise, catalog

AREA_LABELS = {
    "neck": "neck", "shoulder": "shoulder", "elbow": "elbow", "wrist_hand": "wrist/hand", "upper_back": "upper back",
    "lower_back": "lower back", "hip": "hip", "knee": "knee", "ankle_foot": "ankle/foot", "other": "other area",
}

# Duration model (seconds)
WARMUP_S = 300
SECONDS_PER_REP = 3
SET_SETUP_S = 15
TRANSITION_S = 120  # moving to a new station / setting up equipment
SAME_EQUIPMENT_TRANSITION_S = 60  # next exercise uses the same equipment

# (sets, rep_low, rep_high, rest_s) by goal and role
PRESCRIPTIONS = {
    "get_stronger": {"main": (4, 4, 6, 180), "accessory": (3, 8, 10, 90)},
    "build_muscle": {"main": (3, 6, 10, 120), "accessory": (3, 10, 12, 75)},
    "general_fitness": {"main": (3, 8, 12, 90), "accessory": (2, 10, 15, 60)},
    "lose_fat": {"main": (3, 10, 12, 75), "accessory": (2, 12, 15, 45)},
    "muscular_endurance": {"main": (3, 12, 15, 60), "accessory": (2, 15, 20, 45)},
    "cardio_fitness": {"main": (2, 10, 15, 60), "accessory": (2, 12, 15, 45)},
}
TIMED_TARGET_S = {"beginner": 30, "intermediate": 40, "advanced": 45}


@dataclass(frozen=True)
class Limitation:
    body_area: str
    severity: str  # "avoid" | "caution"
    note: str = ""


@dataclass
class TrainingContext:
    equipment: frozenset[str]
    limitations: tuple[Limitation, ...]
    experience: str
    goal: str
    budget_minutes: int
    cardio_minutes: int = 0  # minutes of the session reserved for cardio (0 = none)
    cannot_do_yet: frozenset[str] = frozenset()  # exercise ids the user reported they can't do one rep of
    secondary_goal: str | None = None

    @property
    def available(self) -> frozenset[str]:
        return self.equipment | {"body only"}


@dataclass
class Check:
    ok: bool
    reasons: list[str] = field(default_factory=list)  # why it is not allowed
    notes: list[str] = field(default_factory=list)  # allowed, but flagged for the user


def check_exercise(ex: Exercise, ctx: TrainingContext, enforce_level: bool = True) -> Check:
    reasons, notes = [], []
    missing = [e for e in ex.equipment if e not in ctx.available]
    if missing:
        reasons.append(f"needs {', '.join(missing)}, which is not in your equipment")
    if enforce_level and LEVEL_RANK[ex.level] > EXPERIENCE_MAX_LEVEL[ctx.experience]:
        reasons.append(f"rated {ex.level} in the exercise catalog, above your experience level")
    if ex.id in ctx.cannot_do_yet:
        if enforce_level:
            reasons.append("you reported you can't do one rep yet")
        else:
            notes.append("You reported you can't do one rep of this yet. Choose it only if you want to work on it.")
    for lim in ctx.limitations:
        load = ex.loads.get(lim.body_area, 0)
        area = AREA_LABELS.get(lim.body_area, lim.body_area)
        if not load:
            continue
        if lim.severity == "avoid":
            reasons.append(f"loads the {area}, which you asked Venn to avoid")
        elif load >= 2:
            reasons.append(f"loads the {area} heavily, and you reported the {area} as 'train with caution'")
        else:
            notes.append(f"Loads the {area} moderately. You reported the {area} as 'train with caution': "
                         "use a comfortable range and load, or swap it.")
    return Check(ok=not reasons, reasons=reasons, notes=notes)


def prescription(goal: str, role: str, experience: str, ex: Exercise) -> dict:
    sets, low, high, rest = PRESCRIPTIONS[goal][role]
    if role == "main":
        sets += {"beginner": -1, "intermediate": 0, "advanced": 1}[experience]
    sets = max(2, sets)
    if ex.measure == "time":
        t = TIMED_TARGET_S[experience]
        return {"sets": sets, "rep_low": None, "rep_high": None, "target_seconds": t, "rest_s": min(rest, 60)}
    return {"sets": sets, "rep_low": low, "rep_high": high, "target_seconds": None, "rest_s": rest}


def set_work_seconds(ex: Exercise, rep_high: int | None, target_seconds: int | None) -> int:
    work = (target_seconds or 0) if ex.measure == "time" else (rep_high or 10) * SECONDS_PER_REP
    work += SET_SETUP_S
    return work * (2 if ex.unilateral else 1)


def exercise_seconds(ex: Exercise, sets: int, rep_high: int | None, target_seconds: int | None, rest_s: int) -> int:
    """Working time for all sets plus the rests between them (no rest after the last set)."""
    return sets * set_work_seconds(ex, rep_high, target_seconds) + max(sets - 1, 0) * rest_s


def estimate_seconds(items: list[dict]) -> int:
    """items: dicts with exercise_id, sets, rep_high, target_seconds, rest_s (in workout order).
    Total = warm-up + each exercise + a transition before each exercise (shorter when the
    equipment is unchanged)."""
    cat = catalog()
    total, prev_equipment = WARMUP_S, None
    for it in items:
        ex = cat[it["exercise_id"]]
        total += SAME_EQUIPMENT_TRANSITION_S if ex.equipment == prev_equipment else TRANSITION_S
        total += exercise_seconds(ex, it["sets"], it.get("rep_high"), it.get("target_seconds"), it["rest_s"])
        prev_equipment = ex.equipment
    return total


def validate_plan(items: list[dict], ctx: TrainingContext, enforce_budget: bool = True) -> list[str]:
    """Violations that must block a routine from being shown or saved."""
    cat = catalog()
    violations = []
    seen = set()
    for it in items:
        ex = cat.get(it["exercise_id"])
        if ex is None:
            violations.append(f"unknown exercise '{it['exercise_id']}'")
            continue
        if ex.id in seen:
            violations.append(f"{ex.name} appears twice")
        seen.add(ex.id)
        check = check_exercise(ex, ctx, enforce_level=False)
        violations += [f"{ex.name}: {r}" for r in check.reasons]
        if not 1 <= it["sets"] <= 10:
            violations.append(f"{ex.name}: set count {it['sets']} is outside 1-10")
    all_known = all(it["exercise_id"] in cat for it in items)
    if enforce_budget and items and all_known and estimate_seconds(items) > ctx.budget_minutes * 60:
        violations.append(f"estimated {round(estimate_seconds(items) / 60)} min exceeds the {ctx.budget_minutes}-minute budget")
    return violations


def pattern_label(pattern: str) -> str:
    return PATTERN_LABELS.get(pattern, pattern)
