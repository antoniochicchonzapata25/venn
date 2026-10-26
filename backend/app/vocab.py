"""Allowed values for profile and limitation fields (shared by schemas, services and /api/options)."""

from typing import Literal

Sex = Literal["male", "female", "unspecified"]
ActivityLevel = Literal["sedentary", "light", "moderate", "very", "extra"]
Goal = Literal["lose", "maintain", "gain"]
ProteinLevel = Literal["standard", "high", "very_high"]
DietStyle = Literal["balanced", "lower_carb", "lower_fat"]
TrainingGoal = Literal[
    "build_muscle", "get_stronger", "muscular_endurance", "cardio_fitness", "general_fitness", "lose_fat"
]
GoalFocus = Literal["fat_loss", "recomp", "maintain", "muscle_gain", "lean_gain"]
GymLocation = Literal["commercial_gym", "strength_gym", "local_gym", "home_gym", "minimal", "bodyweight"]
CardioSchedule = Literal["strength_days", "separate_days", "mix", "none"]
EatingPattern = Literal["none", "vegetarian", "vegan", "pescatarian", "other"]
ABILITY_EXERCISES = ("pushups", "pullups", "dips")
ABILITY_LEVELS = ("none", "1_4", "5_9", "10_14", "15_plus", "unsure")
HeightUnit = Literal["cm", "ft_in"]
WeightUnit = Literal["kg", "lb"]
Experience = Literal["beginner", "intermediate", "advanced"]
Split = Literal["auto", "full_body", "upper_lower", "push_pull_legs"]
Units = Literal["metric", "imperial"]
BodyArea = Literal[
    "neck", "shoulder", "elbow", "wrist_hand", "upper_back", "lower_back", "hip", "knee", "ankle_foot", "other"
]
LimitationKind = Literal["temporary", "ongoing"]
LimitationSeverity = Literal["avoid", "caution"]

# Equipment names match free-exercise-db so the Phase 3 generator can filter directly.
EQUIPMENT = (
    "body only", "dumbbell", "barbell", "kettlebells", "cable", "machine", "bands",
    "e-z curl bar", "medicine ball", "exercise ball", "foam roll", "bench", "pull-up bar", "other",
)
DIETARY_PREFERENCES = (
    "vegetarian", "vegan", "pescatarian", "dairy_free", "gluten_free", "nut_free", "halal", "kosher",
)
