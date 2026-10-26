"""Build Venn's curated exercise catalog from free-exercise-db (public domain, The Unlicense).

    python scripts/build_exercise_catalog.py path/to/exercises.json
    (download: https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json)

free-exercise-db supplies each exercise's name, equipment, level, mechanic, muscles and
instructions. Venn adds, per exercise (the CURATION table below):

- pattern: the movement slot it fills in a workout (squat, hinge, push_h, ...);
- extra equipment the source does not list (a bench or a pull-up bar);
- measure: "reps" or "time";
- unilateral: whether each set is done once per side (it takes about twice as long);
- loads: which body areas the movement loads, 1 = moderately, 2 = heavily.

The "loads" tags are general exercise-science descriptions of where a movement puts load.
Venn uses them only to filter or flag exercises for areas a user has reported. They are not
a medical judgement of whether an exercise is safe for anyone.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "exercises.json"

# id: (pattern, extra equipment, measure, unilateral, loads)
CURATION: dict[str, tuple[str, list[str], str, bool, dict[str, int]]] = {
    # squat pattern
    "Barbell_Squat": ("squat", [], "reps", False, {"lower_back": 2, "knee": 2, "hip": 1}),
    "Goblet_Squat": ("squat", [], "reps", False, {"knee": 1, "hip": 1}),
    "Leg_Press": ("squat", [], "reps", False, {"knee": 1, "hip": 1, "lower_back": 1}),
    "Dumbbell_Squat": ("squat", [], "reps", False, {"knee": 1, "lower_back": 1}),
    "Hack_Squat": ("squat", [], "reps", False, {"knee": 2}),
    "Smith_Machine_Squat": ("squat", [], "reps", False, {"knee": 2, "lower_back": 1}),
    "Barbell_Full_Squat": ("squat", [], "reps", False, {"lower_back": 2, "knee": 2, "hip": 2}),
    "Front_Barbell_Squat": ("squat", [], "reps", False, {"knee": 2, "wrist_hand": 1, "lower_back": 1}),
    "Bodyweight_Squat": ("squat", [], "reps", False, {"knee": 1}),
    # hinge pattern
    "Romanian_Deadlift": ("hinge", [], "reps", False, {"lower_back": 2, "hip": 1}),
    "Barbell_Hip_Thrust": ("hinge", ["bench"], "reps", False, {"hip": 1, "lower_back": 1}),
    "Barbell_Deadlift": ("hinge", [], "reps", False, {"lower_back": 2, "hip": 1, "wrist_hand": 1}),
    "Stiff-Legged_Dumbbell_Deadlift": ("hinge", [], "reps", False, {"lower_back": 2, "hip": 1}),
    "Kettlebell_One-Legged_Deadlift": ("hinge", [], "reps", True, {"lower_back": 1, "hip": 1, "ankle_foot": 1}),
    "One-Arm_Kettlebell_Swings": ("hinge", [], "reps", False, {"lower_back": 2, "shoulder": 1}),
    "Good_Morning": ("hinge", [], "reps", False, {"lower_back": 2}),
    "Band_Good_Morning": ("hinge", [], "reps", False, {"lower_back": 1}),
    "Butt_Lift_Bridge": ("hinge", [], "reps", False, {}),
    "Single_Leg_Glute_Bridge": ("hinge", [], "reps", True, {"hip": 1}),
    # single-leg
    "Split_Squat_with_Dumbbells": ("lunge", [], "reps", True, {"knee": 2, "hip": 1}),
    "Dumbbell_Lunges": ("lunge", [], "reps", True, {"knee": 2, "hip": 1, "ankle_foot": 1}),
    "Dumbbell_Rear_Lunge": ("lunge", [], "reps", True, {"knee": 1, "hip": 1}),
    "Barbell_Lunge": ("lunge", [], "reps", True, {"knee": 2, "hip": 1, "lower_back": 1}),
    "Dumbbell_Step_Ups": ("lunge", ["bench"], "reps", True, {"knee": 2, "ankle_foot": 1}),
    "Bodyweight_Walking_Lunge": ("lunge", [], "reps", True, {"knee": 2, "ankle_foot": 1}),
    "Glute_Kickback": ("lunge", [], "reps", True, {"hip": 1}),
    # leg isolation
    "Lying_Leg_Curls": ("knee_flex", [], "reps", False, {"knee": 1}),
    "Seated_Leg_Curl": ("knee_flex", [], "reps", False, {"knee": 1}),
    "Leg_Extensions": ("knee_ext", [], "reps", False, {"knee": 2}),
    "Standing_Calf_Raises": ("calf", [], "reps", False, {"ankle_foot": 1, "lower_back": 1}),
    "Seated_Calf_Raise": ("calf", [], "reps", False, {"ankle_foot": 1}),
    "Calf_Raise_On_A_Dumbbell": ("calf", [], "reps", True, {"ankle_foot": 2}),
    # horizontal push
    "Barbell_Bench_Press_-_Medium_Grip": ("push_h", ["bench"], "reps", False, {"shoulder": 2, "elbow": 1, "wrist_hand": 1}),
    "Dumbbell_Bench_Press": ("push_h", ["bench"], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Incline_Dumbbell_Press": ("push_h", ["bench"], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Machine_Bench_Press": ("push_h", [], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Dumbbell_Floor_Press": ("push_h", [], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Pushups": ("push_h", [], "reps", False, {"wrist_hand": 2, "shoulder": 1, "elbow": 1}),
    "Cable_Crossover": ("chest_fly", [], "reps", False, {"shoulder": 1}),
    "Dumbbell_Flyes": ("chest_fly", ["bench"], "reps", False, {"shoulder": 2}),
    # vertical push
    "Seated_Dumbbell_Press": ("push_v", ["bench"], "reps", False, {"shoulder": 2, "elbow": 1}),
    "Machine_Shoulder_Military_Press": ("push_v", [], "reps", False, {"shoulder": 2, "elbow": 1}),
    "Standing_Military_Press": ("push_v", [], "reps", False, {"shoulder": 2, "lower_back": 1, "wrist_hand": 1}),
    "Dumbbell_Shoulder_Press": ("push_v", [], "reps", False, {"shoulder": 2, "elbow": 1}),
    "Arnold_Dumbbell_Press": ("push_v", ["bench"], "reps", False, {"shoulder": 2, "elbow": 1}),
    "Side_Lateral_Raise": ("lateral", [], "reps", False, {"shoulder": 1}),
    "Cable_Seated_Lateral_Raise": ("lateral", [], "reps", False, {"shoulder": 1}),
    # vertical pull
    "Wide-Grip_Lat_Pulldown": ("pull_v", [], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Close-Grip_Front_Lat_Pulldown": ("pull_v", [], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Pullups": ("pull_v", ["pull-up bar"], "reps", False, {"shoulder": 1, "elbow": 1}),
    "Chin-Up": ("pull_v", ["pull-up bar"], "reps", False, {"shoulder": 1, "elbow": 2}),
    # horizontal pull
    "Seated_Cable_Rows": ("pull_h", [], "reps", False, {"lower_back": 1, "elbow": 1}),
    "One-Arm_Dumbbell_Row": ("pull_h", ["bench"], "reps", True, {"elbow": 1}),
    "Leverage_Iso_Row": ("pull_h", [], "reps", False, {"elbow": 1}),
    "Bent_Over_Barbell_Row": ("pull_h", [], "reps", False, {"lower_back": 2, "elbow": 1}),
    "Bent_Over_Two-Dumbbell_Row": ("pull_h", [], "reps", False, {"lower_back": 2, "elbow": 1}),
    "Inverted_Row": ("pull_h", ["barbell"], "reps", False, {"shoulder": 1, "elbow": 1}),
    # rear delts / upper back
    "Face_Pull": ("rear_delt", [], "reps", False, {"shoulder": 1}),
    "Reverse_Flyes": ("rear_delt", [], "reps", False, {"shoulder": 1, "lower_back": 1}),
    "Band_Pull_Apart": ("rear_delt", [], "reps", False, {"shoulder": 1}),
    # arms
    "Dumbbell_Bicep_Curl": ("biceps", [], "reps", False, {"elbow": 1}),
    "Hammer_Curls": ("biceps", [], "reps", False, {"elbow": 1, "wrist_hand": 1}),
    "Cable_Hammer_Curls_-_Rope_Attachment": ("biceps", [], "reps", False, {"elbow": 1}),
    "Barbell_Curl": ("biceps", [], "reps", False, {"elbow": 1, "wrist_hand": 1}),
    "EZ-Bar_Curl": ("biceps", [], "reps", False, {"elbow": 1}),
    "Triceps_Pushdown_-_Rope_Attachment": ("triceps", [], "reps", False, {"elbow": 1}),
    "Triceps_Pushdown": ("triceps", [], "reps", False, {"elbow": 1}),
    "Standing_Dumbbell_Triceps_Extension": ("triceps", [], "reps", False, {"elbow": 1, "shoulder": 1}),
    "EZ-Bar_Skullcrusher": ("triceps", ["bench"], "reps", False, {"elbow": 2}),
    "Bench_Dips": ("triceps", ["bench"], "reps", False, {"shoulder": 2, "wrist_hand": 1, "elbow": 1}),
    "Push-Ups_-_Close_Triceps_Position": ("triceps", [], "reps", False, {"wrist_hand": 2, "elbow": 1}),
    # core
    "Plank": ("core", [], "time", False, {"lower_back": 1}),
    "Dead_Bug": ("core", [], "reps", False, {}),
    "Pallof_Press": ("core", [], "reps", False, {}),
    "Side_Bridge": ("core", [], "time", True, {"shoulder": 1}),
    "Crunches": ("core", [], "reps", False, {"neck": 1}),
    "Cable_Crunch": ("core", [], "reps", False, {"lower_back": 1}),
    "Russian_Twist": ("core", [], "reps", False, {"lower_back": 2}),
    "Ab_Roller": ("core", [], "reps", False, {"lower_back": 2, "shoulder": 1}),
    "Hanging_Leg_Raise": ("core", ["pull-up bar"], "reps", False, {"shoulder": 1, "lower_back": 1}),
}


def short_instructions(steps: list[str], limit: int = 2) -> list[str]:
    out = []
    for s in steps[:limit]:
        s = s.replace("�", "").strip()
        out.append(s if len(s) <= 220 else s[:217].rsplit(" ", 1)[0] + "...")
    return out


def main(src: Path) -> int:
    source = {x["id"]: x for x in json.loads(src.read_text(encoding="utf-8"))}
    exercises = []
    for ex_id, (pattern, extra, measure, unilateral, loads) in CURATION.items():
        x = source[ex_id]
        equipment = [x["equipment"] or "body only", *extra]
        exercises.append({
            "id": ex_id, "name": x["name"], "pattern": pattern,
            "equipment": sorted(set(equipment) - {"body only"}) or ["body only"],
            "level": x["level"], "mechanic": x.get("mechanic") or "compound",
            "primary_muscles": x["primaryMuscles"], "secondary_muscles": x["secondaryMuscles"],
            "instructions": short_instructions(x["instructions"]),
            "measure": measure, "unilateral": unilateral, "loads": loads,
        })
    # Venn-defined entry (not from free-exercise-db): a cardio block the user fills with any modality.
    exercises.append({
        "id": "Cardio_Session", "name": "Cardio (your choice)", "pattern": "cardio", "equipment": ["body only"],
        "level": "beginner", "mechanic": "compound", "primary_muscles": ["cardiovascular system"], "secondary_muscles": [],
        "instructions": ["Choose a bike, rower, elliptical, brisk walk or run.",
                         "Keep an easy-to-moderate pace: you can talk in short sentences."],
        "measure": "time", "unilateral": False, "loads": {},
    })
    payload = {
        "source": "free-exercise-db by yuhonas (https://github.com/yuhonas/free-exercise-db), The Unlicense (public domain)",
        "curation": "pattern, extra equipment, measure, unilateral and loads tags added by Venn (scripts/build_exercise_catalog.py)",
        "exercises": exercises,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} with {len(exercises)} exercises")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
