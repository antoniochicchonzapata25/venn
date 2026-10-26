"""The bundled exercise catalog (backend/app/data/exercises.json), kept in memory.

Built by scripts/build_exercise_catalog.py from free-exercise-db (public domain).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CATALOG_FILE = Path(__file__).resolve().parents[1] / "data" / "exercises.json"

LEVEL_RANK = {"beginner": 0, "intermediate": 1, "expert": 2}
EXPERIENCE_MAX_LEVEL = {"beginner": 0, "intermediate": 1, "advanced": 2}

PATTERN_LABELS = {
    "squat": "squat", "hinge": "hip hinge", "lunge": "single-leg", "knee_flex": "hamstring curl",
    "knee_ext": "leg extension", "calf": "calf raise", "push_h": "horizontal press", "chest_fly": "chest fly",
    "push_v": "overhead press", "lateral": "lateral raise", "pull_v": "vertical pull", "pull_h": "row",
    "rear_delt": "rear delt / upper back", "biceps": "biceps", "triceps": "triceps", "core": "core", "cardio": "cardio",
}
LOWER_BODY_PATTERNS = {"squat", "hinge", "lunge", "knee_flex", "knee_ext", "calf"}


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    pattern: str
    equipment: tuple[str, ...]
    level: str
    mechanic: str
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    instructions: tuple[str, ...]
    measure: str  # "reps" | "time"
    unilateral: bool
    loads: dict  # body area -> 1 (moderate) | 2 (heavy)

    def summary(self) -> dict:
        return {
            "id": self.id, "name": self.name, "pattern": self.pattern, "pattern_label": PATTERN_LABELS[self.pattern],
            "equipment": list(self.equipment), "level": self.level, "mechanic": self.mechanic,
            "primary_muscles": list(self.primary_muscles), "measure": self.measure, "unilateral": self.unilateral,
            "instructions": list(self.instructions),
        }


@lru_cache(maxsize=1)
def catalog() -> dict[str, Exercise]:
    data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    out = {}
    for e in data["exercises"]:
        out[e["id"]] = Exercise(
            id=e["id"], name=e["name"], pattern=e["pattern"], equipment=tuple(e["equipment"]), level=e["level"],
            mechanic=e["mechanic"], primary_muscles=tuple(e["primary_muscles"]),
            secondary_muscles=tuple(e["secondary_muscles"]), instructions=tuple(e["instructions"]),
            measure=e["measure"], unilateral=e["unilateral"], loads=dict(e["loads"]),
        )
    return out


def by_pattern(pattern: str) -> list[Exercise]:
    """Exercises for a pattern in curated order (most standard first)."""
    return [e for e in catalog().values() if e.pattern == pattern]


SOURCE = "free-exercise-db (public domain), curated by Venn"
