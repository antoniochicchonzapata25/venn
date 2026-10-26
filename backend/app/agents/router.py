"""Choose a workflow. Keyword rules first (free, deterministic); a tiny model call only when unclear."""

from __future__ import annotations

import re

WORKFLOWS = ("nutrition", "training", "progress")

NUTRITION_WORDS = r"protein|calorie|kcal|carb|fat\b|fats|food|foods|eat|ate|eating|meal|meals|macro|diet|nutrition|snack|breakfast|lunch|dinner"
TRAINING_WORDS = (r"workout|workouts|exercise|exercises|train|training|split|sets?\b|reps?\b|squat|bench|deadlift|press|row|"
                  r"replace|alternative|swap|routine|gym|cardio|lift|lifting|strength|equipment|session")
PROGRESS_WORDS = r"progress|trend|consistent|consistently|overall|improve|struggling|pattern|both|week|weeks|month|change"


def keyword_route(question: str) -> str | None:
    q = question.lower()
    nut = len(re.findall(rf"\b(?:{NUTRITION_WORDS})", q))
    tr = len(re.findall(rf"\b(?:{TRAINING_WORDS})", q))
    prog = len(re.findall(rf"\b(?:{PROGRESS_WORDS})", q))
    if nut and tr:
        return "progress"  # cross-domain questions need both kinds of data
    if prog and (nut or tr) and re.search(r"\b(?:progress|struggling|consistent|consistently|overall|pattern)\b", q):
        return "progress"
    if nut:
        return "nutrition"
    if tr:
        return "training"
    if prog:
        return "progress"
    return None


ROUTER_INSTRUCTIONS = ("Classify the fitness-app question into exactly one word: nutrition, training or progress. "
                       "progress = needs both nutrition and training data, or overall progress. Reply with the one word only.")


def parse_route(text: str) -> str:
    word = (text or "").strip().lower().split()
    first = re.sub(r"[^a-z]", "", word[0]) if word else ""
    return first if first in WORKFLOWS else "progress"
