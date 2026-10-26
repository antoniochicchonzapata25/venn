"""Deterministic workout generator (works with no AI key).

Steps:
1. Pick the split (preferred, or by days per week) and the day type (requested, or the next in rotation).
2. Fill each template slot with the best compatible exercise (equipment, reported
   limitations, experience level; the user's past swaps break ties).
3. Prescribe sets, reps and rest from the training goal and experience.
4. Fit the time budget: drop the lowest-priority slots, then trim sets, until the estimate
   (warm-up + sets + rests + transitions) fits. Group accessories by equipment to cut changeovers.
5. Validate the finished plan with workout_rules.validate_plan before returning it.

A future Training Agent may rank or explain options, but it must pass the same validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.exercises import LOWER_BODY_PATTERNS, Exercise, by_pattern, catalog
from app.services.workout_rules import (
    AREA_LABELS, SET_SETUP_S, TRANSITION_S, TrainingContext, check_exercise, estimate_seconds, exercise_seconds, pattern_label,
    prescription, validate_plan,
)


def catalog_lookup(exercise_id: str) -> Exercise | None:
    return catalog().get(exercise_id)

GENERATOR_VERSION = "deterministic-v1"

SPLITS = {
    "full_body": ["full_body"],
    "upper_lower": ["upper", "lower"],
    "push_pull_legs": ["push", "pull", "legs"],
}
DAY_NAMES = {"full_body": "Full Body", "upper": "Upper Body", "lower": "Lower Body", "push": "Push", "pull": "Pull", "legs": "Legs"}
SPLIT_NAMES = {"full_body": "full-body", "upper_lower": "upper/lower", "push_pull_legs": "push/pull/legs"}
GOAL_OBJECTIVES = {
    "build_muscle": "Build muscle: moderate loads for 6-12 reps, taking working sets close to failure.",
    "get_stronger": "Get stronger: heavier main lifts for 4-6 reps with longer rest, plus supporting accessories.",
    "general_fitness": "General fitness: balanced full-range work for 8-15 reps with moderate rest.",
    "lose_fat": "Lose fat while keeping muscle: higher reps and shorter rest to keep the session dense.",
    "muscular_endurance": "Muscular endurance: lighter loads for 12-20 reps with short rest.",
    "cardio_fitness": "Cardiovascular fitness: efficient strength work for 10-15 reps, plus planned cardio.",
}
GOAL_NAMES = {"build_muscle": "muscle gain", "get_stronger": "strength", "muscular_endurance": "muscular endurance",
              "cardio_fitness": "cardiovascular fitness", "general_fitness": "general fitness", "lose_fat": "fat loss"}
MIN_STRENGTH_MINUTES = 20

# (patterns to try in order, role, priority) - priority 1 is kept longest when trimming for time
TEMPLATES: dict[str, list[tuple[tuple[str, ...], str, int]]] = {
    "full_body": [(("squat", "lunge"), "main", 1), (("push_h",), "main", 1), (("pull_h", "pull_v"), "main", 1),
                  (("hinge",), "main", 2), (("push_v",), "accessory", 2), (("pull_v", "pull_h"), "accessory", 3),
                  (("core",), "accessory", 2), (("lateral", "biceps"), "accessory", 3)],
    "upper": [(("push_h",), "main", 1), (("pull_v", "pull_h"), "main", 1), (("push_v",), "main", 2),
              (("pull_h", "pull_v"), "main", 2), (("lateral",), "accessory", 3), (("triceps",), "accessory", 3),
              (("biceps",), "accessory", 3), (("rear_delt",), "accessory", 3)],
    "lower": [(("squat", "lunge"), "main", 1), (("hinge",), "main", 1), (("lunge", "squat"), "main", 2),
              (("knee_flex",), "accessory", 2), (("core",), "accessory", 2), (("calf",), "accessory", 3),
              (("knee_ext",), "accessory", 3)],
    "push": [(("push_h",), "main", 1), (("push_v",), "main", 1), (("push_h",), "accessory", 2),
             (("lateral",), "accessory", 2), (("triceps",), "accessory", 2), (("chest_fly",), "accessory", 3),
             (("triceps",), "accessory", 3)],
    "pull": [(("pull_v", "pull_h"), "main", 1), (("pull_h", "pull_v"), "main", 1), (("pull_h", "pull_v"), "accessory", 2),
             (("rear_delt",), "accessory", 2), (("biceps",), "accessory", 2), (("biceps",), "accessory", 3),
             (("core",), "accessory", 3)],
    "legs": [(("squat", "lunge"), "main", 1), (("hinge",), "main", 1), (("lunge", "squat"), "accessory", 2),
             (("knee_flex",), "accessory", 2), (("calf",), "accessory", 3), (("knee_ext",), "accessory", 3),
             (("core",), "accessory", 3)],
}
MIN_EXERCISES = 2


class GenerationError(ValueError):
    """The constraints leave no useful routine; carries suggestions for the user."""

    def __init__(self, message: str, alternatives: list[str]):
        super().__init__(message)
        self.message = message
        self.alternatives = alternatives


@dataclass
class History:
    completed_by_split: dict[str, int] = field(default_factory=dict)
    swapped_in: dict[str, int] = field(default_factory=dict)  # exercise id -> times chosen as a replacement
    swapped_out: dict[str, int] = field(default_factory=dict)  # exercise id -> times replaced away
    last_sets: dict[str, list[tuple[float | None, int | None]]] = field(default_factory=dict)  # (weight_kg, reps)
    last_targets: dict[str, int] = field(default_factory=dict)  # exercise id -> rep_high last prescribed


@dataclass
class PlanItem:
    exercise: Exercise
    role: str
    slot_patterns: tuple[str, ...]
    priority: int
    sets: int
    rep_low: int | None
    rep_high: int | None
    target_seconds: int | None
    rest_s: int
    notes: list[str]
    suggested_weight_kg: float | None = None
    last_summary: str | None = None

    def as_rule_item(self) -> dict:
        return {"exercise_id": self.exercise.id, "sets": self.sets, "rep_high": self.rep_high,
                "target_seconds": self.target_seconds, "rest_s": self.rest_s}

    @property
    def est_seconds(self) -> int:
        return exercise_seconds(self.exercise, self.sets, self.rep_high, self.target_seconds, self.rest_s)


@dataclass
class Plan:
    name: str
    split: str
    day_type: str
    objective: str
    items: list[PlanItem]
    est_seconds: int
    explanation: list[str]
    generator: str = GENERATOR_VERSION


def choose_split(preferred: str, days_per_week: int) -> tuple[str, str]:
    if preferred in SPLITS:
        return preferred, f"your preferred {SPLIT_NAMES[preferred]} split"
    if days_per_week <= 3:
        return "full_body", f"a full-body split, which suits {days_per_week} training days a week"
    if days_per_week == 4:
        return "upper_lower", "an upper/lower split, which suits 4 training days a week"
    return "push_pull_legs", f"a push/pull/legs split, which suits {days_per_week} training days a week"


def next_day_type(split: str, history: History) -> str:
    days = SPLITS[split]
    return days[history.completed_by_split.get(split, 0) % len(days)]


def round_weight(kg: float) -> float:
    return round(kg * 2) / 2  # nearest 0.5 kg


def weight_suggestion(ex: Exercise, history: History) -> tuple[float | None, str | None]:
    """Simple double progression: same weight next time, or +2.5 kg upper / +5 kg lower body
    when every set last time reached the top of the rep range."""
    sets = [s for s in history.last_sets.get(ex.id, []) if s[0]]
    if not sets:
        return None, None
    top = max(w for w, _ in sets)
    reps = [r for w, r in sets if w == top and r is not None]
    summary = f"Last time: {top:g} kg x " + ", ".join(str(r) for r in reps)
    target_high = history.last_targets.get(ex.id)
    if target_high and reps and all(r >= target_high for r in reps):
        step = 5.0 if ex.pattern in LOWER_BODY_PATTERNS else 2.5
        return round_weight(top + step), summary + f" (all sets hit {target_high}; +{step:g} kg)"
    return round_weight(top), summary


def candidates(patterns: tuple[str, ...], ctx: TrainingContext, history: History, used: set[str]) -> list[tuple[Exercise, list[str]]]:
    out = []
    for p in patterns:
        ranked = []
        for idx, ex in enumerate(by_pattern(p)):
            if ex.id in used:
                continue
            check = check_exercise(ex, ctx)
            if not check.ok:
                continue
            score = -idx + 3 * history.swapped_in.get(ex.id, 0) - 3 * history.swapped_out.get(ex.id, 0) - 0.5 * len(check.notes)
            ranked.append((score, idx, ex, check.notes))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        out += [(ex, notes) for _, _, ex, notes in ranked]
        if out:
            break  # first pattern with any compatible exercise wins
    return out


def generate(*, ctx: TrainingContext, preferred_split: str, days_per_week: int, history: History,
             day_type: str | None = None, variant: int = 0) -> Plan:
    split, split_reason = choose_split(preferred_split, days_per_week)
    if day_type is not None and day_type not in TEMPLATES:
        raise GenerationError(f"Unknown workout type '{day_type}'.", [f"Choose one of: {', '.join(TEMPLATES)}"])
    day = day_type or next_day_type(split, history)
    explanation = [f"Venn used {split_reason}; this is the {DAY_NAMES[day]} day."]

    items: list[PlanItem] = []
    used: set[str] = set()
    omitted: list[str] = []
    for slot_no, (patterns, role, priority) in enumerate(TEMPLATES[day]):
        options = candidates(patterns, ctx, history, used)
        if not options:
            omitted.append(pattern_label(patterns[0]))
            continue
        pick = options[(variant + slot_no) % min(len(options), 2)] if variant else options[0]
        ex, notes = pick
        used.add(ex.id)
        rx = prescription(ctx.goal, role, ctx.experience, ex)
        weight, last = weight_suggestion(ex, history)
        items.append(PlanItem(ex, role, patterns, priority, rx["sets"], rx["rep_low"], rx["rep_high"],
                              rx["target_seconds"], rx["rest_s"], notes, weight, last))

    if not any(i.priority == 1 for i in items) or len(items) < MIN_EXERCISES:
        raise GenerationError(
            f"Venn couldn't build a useful {DAY_NAMES[day]} workout with your current equipment and reported limitations.",
            ["Add the equipment you can use in Settings (for example dumbbells, a bench or bands).",
             "Try a different workout type, such as Full Body.",
             "Review your limitations in Settings: 'avoid' excludes every exercise that loads that area."])

    # Reserve part of the session for cardio if the user asked for it, keeping at least 20 min of strength work.
    # (about 25 min of strength work plus a changeover must remain; cardio blocks shorter than 10 min are skipped)
    cardio_min = min(ctx.cardio_minutes, ctx.budget_minutes - MIN_STRENGTH_MINUTES - 8) if ctx.cardio_minutes else 0
    cardio_ex = catalog_lookup("Cardio_Session") if cardio_min >= 10 else None
    budget = ctx.budget_minutes * 60 - (cardio_min * 60 + TRANSITION_S + SET_SETUP_S if cardio_ex else 0)
    dropped: list[str] = []

    def total() -> int:
        return estimate_seconds([i.as_rule_item() for i in order(items)])

    # Drop the lowest-priority, latest slots first.
    while total() > budget and len(items) > MIN_EXERCISES:
        drop_candidates = [i for i in items if i.priority > 1] or [i for i in items if i.role == "accessory"]
        if not drop_candidates:
            break
        victim = max(drop_candidates, key=lambda i: (i.priority, items.index(i)))
        items.remove(victim)
        dropped.append(victim.exercise.name)
    # Then trim sets (accessories first, never below 2).
    while total() > budget:
        trimmable = [i for i in items if i.sets > 2]
        if not trimmable:
            break
        target = max(trimmable, key=lambda i: (i.role == "accessory", i.sets))
        target.sets -= 1
    if total() > budget:
        minimum = -(-total() // 60)
        raise GenerationError(
            f"Even the shortest version of this workout needs about {minimum} minutes, more than your {ctx.budget_minutes}.",
            [f"Generate with {minimum} minutes or more.", "Choose Full Body, which can be shorter."])

    items = order(items)
    if cardio_ex:
        items.append(PlanItem(cardio_ex, "accessory", ("cardio",), 1, 1, None, None, cardio_min * 60, 0,
                              ["Pick any cardio you like (bike, rower, elliptical, brisk walk or run) at an easy-to-moderate "
                               "pace" + (", choosing one that suits the limitations you reported." if ctx.limitations else ".")]))
    est = estimate_seconds([i.as_rule_item() for i in items])
    violations = validate_plan([i.as_rule_item() for i in items], ctx)
    if violations:  # cannot happen if the generator is correct; never return an invalid plan
        raise GenerationError("The generated workout failed validation: " + "; ".join(violations), [])

    if cardio_ex:
        explanation.append(f"You asked for cardio in your plan: the last {cardio_min} min are a cardio block.")
    elif ctx.cardio_minutes:
        explanation.append("Your session is too short to add a cardio block of at least 10 min while keeping enough time for strength work.")
    if ctx.secondary_goal and ctx.secondary_goal != ctx.goal:
        explanation.append(f"Primary goal {GOAL_NAMES[ctx.goal]} sets the sets, reps and rest; your secondary goal "
                           f"({GOAL_NAMES[ctx.secondary_goal]}) is noted for your coach.")
    explanation.append(
        f"Estimated {round(est / 60)} min of your {ctx.budget_minutes}-minute budget: 5 min warm-up, "
        f"{sum(i.sets for i in items)} sets with rest, and changeovers between exercises. "
        "Accessories using the same equipment are grouped to save time.")
    gear = sorted(ctx.equipment - {"body only"})
    explanation.append("Uses only equipment you listed: " + (", ".join(gear) + ", and body weight." if gear else "body weight."))
    for lim in ctx.limitations:
        area = AREA_LABELS.get(lim.body_area, lim.body_area)
        if lim.body_area == "other":
            explanation.append(f"You reported a limitation ({lim.note or 'other area'}) that Venn can't match to exercises "
                               "automatically. Please review each exercise and swap any that don't suit you.")
        elif lim.severity == "avoid":
            explanation.append(f"You asked to avoid loading the {area}: every exercise that loads it was excluded.")
        else:
            explanation.append(f"You reported the {area} as 'train with caution': exercises that load it heavily were "
                               "excluded, and any that load it moderately are flagged.")
    if omitted:
        explanation.append("No compatible exercise for: " + ", ".join(omitted) + "; those slots were left out.")
    if dropped:
        explanation.append("Dropped to fit your time: " + ", ".join(dropped) + ".")
    if any(i.suggested_weight_kg for i in items):
        explanation.append("Suggested weights come from your last logged sets.")
    explanation.append("This is general fitness guidance, not medical advice. Stop any exercise that causes pain.")

    return Plan(name=f"{DAY_NAMES[day]}", split=split, day_type=day, objective=GOAL_OBJECTIVES[ctx.goal],
                items=items, est_seconds=est, explanation=explanation)


def order(items: list[PlanItem]) -> list[PlanItem]:
    """Main lifts in template order, then accessories grouped by equipment (stable)."""
    mains = [i for i in items if i.role == "main"]
    acc = [i for i in items if i.role == "accessory"]
    first_seen: dict[tuple[str, ...], int] = {}
    for n, i in enumerate(acc):
        first_seen.setdefault(i.exercise.equipment, n)
    acc.sort(key=lambda i: first_seen[i.exercise.equipment])
    return mains + acc


def alternatives(current: Exercise, ctx: TrainingContext, exclude: set[str], slot_patterns: tuple[str, ...] | None = None,
                 limit: int = 6) -> list[dict]:
    """Compatible replacements: same pattern first, then the slot's other patterns. Each carries its notes."""
    patterns = [current.pattern] + [p for p in (slot_patterns or ()) if p != current.pattern]
    out = []
    for p in patterns:
        for ex in by_pattern(p):
            if ex.id == current.id or ex.id in exclude:
                continue
            check = check_exercise(ex, ctx, enforce_level=False)
            if not check.ok:
                continue
            same = "Same movement pattern" if p == current.pattern else f"Similar slot ({pattern_label(p)})"
            out.append({"exercise": ex, "reason": f"{same}: {pattern_label(p)}; trains {', '.join(ex.primary_muscles)}.",
                        "notes": check.notes})
    return out[:limit]
