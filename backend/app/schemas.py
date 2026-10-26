"""Request and response models. Validation here is the first line of defense; services re-check."""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.targets import HEIGHT_RANGE_CM, MAX_AGE, MAX_RATE_PCT, MIN_AGE, WEIGHT_RANGE_KG
from app.vocab import (
    ABILITY_EXERCISES, ABILITY_LEVELS, DIETARY_PREFERENCES, EQUIPMENT, ActivityLevel, BodyArea, CardioSchedule, DietStyle,
    EatingPattern, Experience, Goal, GoalFocus, GymLocation, HeightUnit,
    LimitationKind, LimitationSeverity, ProteinLevel, Sex, Split, TrainingGoal, Units, WeightUnit,
)

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- auth ----------

class RegisterIn(Strict):
    username: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=60)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.fullmatch(v):
            raise ValueError("username must be 3-32 characters: lowercase letters, digits or _")
        return v


class LoginIn(Strict):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str


# ---------- profile ----------

def _clean_choices(values: list[str], allowed: tuple[str, ...], label: str) -> list[str]:
    seen: list[str] = []
    for v in values:
        if v not in allowed:
            raise ValueError(f"unknown {label}: {v!r}")
        if v not in seen:
            seen.append(v)
    return seen


class ProfileIn(Strict):
    sex: Sex
    birth_year: int
    height_cm: float = Field(ge=HEIGHT_RANGE_CM[0], le=HEIGHT_RANGE_CM[1])
    weight_kg: float = Field(ge=WEIGHT_RANGE_KG[0], le=WEIGHT_RANGE_KG[1])
    activity_level: ActivityLevel
    goal: Goal
    goal_rate_pct: float = Field(default=0.0, ge=0)
    protein_level: ProteinLevel = "standard"
    diet_style: DietStyle = "balanced"
    dietary_preferences: list[str] = Field(default_factory=list, max_length=len(DIETARY_PREFERENCES))
    training_goal: TrainingGoal
    experience: Experience
    days_per_week: int = Field(ge=1, le=7)
    session_minutes: int = Field(ge=15, le=180)
    equipment: list[str] = Field(default_factory=list, max_length=len(EQUIPMENT))
    preferred_split: Split = "auto"
    units: Units | None = None  # legacy; derived from weight_unit when omitted
    # Added in Milestone 3.5 (all optional, so older clients keep working)
    secondary_training_goal: TrainingGoal | None = None
    cardio_sessions_per_week: int = Field(default=0, ge=0, le=14)
    cardio_minutes: int | None = Field(default=None, ge=5, le=180)
    cardio_in_plan: bool = False
    goal_focus: GoalFocus | None = None
    target_weight_kg: float | None = Field(default=None, ge=WEIGHT_RANGE_KG[0], le=WEIGHT_RANGE_KG[1])
    target_date: date | None = None
    body_fat_pct: float | None = Field(default=None, ge=3, le=60)
    height_unit: HeightUnit = "cm"
    weight_unit: WeightUnit | None = None
    # Added in Milestone 3.6 (optional)
    gym_location: GymLocation | None = None
    cardio_schedule: CardioSchedule | None = None
    eating_pattern: EatingPattern | None = None
    eating_pattern_other: str | None = Field(default=None, max_length=120)
    exercise_ability: dict[str, str] | None = None

    @field_validator("exercise_ability")
    @classmethod
    def _ability(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return None
        for k, level in v.items():
            if k not in ABILITY_EXERCISES:
                raise ValueError(f"unknown exercise '{k}'")
            if level not in ABILITY_LEVELS:
                raise ValueError(f"unknown ability level '{level}'")
        return v

    @field_validator("eating_pattern_other")
    @classmethod
    def _other(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = "".join(ch for ch in v if ch.isprintable()).strip()
        return v or None

    @field_validator("birth_year")
    @classmethod
    def _adult(cls, v: int) -> int:
        age = date.today().year - v
        if not MIN_AGE <= age <= MAX_AGE:
            raise ValueError(f"Venn is for adults: age must be between {MIN_AGE} and {MAX_AGE}")
        return v

    @field_validator("dietary_preferences")
    @classmethod
    def _diet(cls, v: list[str]) -> list[str]:
        return _clean_choices(v, DIETARY_PREFERENCES, "dietary preference")

    @field_validator("equipment")
    @classmethod
    def _equipment(cls, v: list[str]) -> list[str]:
        return _clean_choices(v, EQUIPMENT, "equipment")

    @model_validator(mode="after")
    def _rate_matches_goal(self) -> ProfileIn:
        limit = MAX_RATE_PCT[self.goal]
        if self.goal == "maintain":
            self.goal_rate_pct = 0.0
        elif self.goal_rate_pct > limit:
            raise ValueError(f"goal rate for '{self.goal}' must be at most {limit}% of body weight per week")
        # Units: keep the legacy `units` field and the per-field weight unit consistent.
        if self.weight_unit is None:
            self.weight_unit = "lb" if self.units == "imperial" else "kg"
        self.units = "imperial" if self.weight_unit == "lb" else "metric"
        # A target weight only makes sense with a scale-weight goal, in the right direction.
        if self.goal == "maintain":
            self.target_weight_kg, self.target_date = None, None
        elif self.target_weight_kg is not None:
            if self.goal == "lose" and self.target_weight_kg >= self.weight_kg:
                raise ValueError("target weight must be below your current weight when your goal is to lose weight")
            if self.goal == "gain" and self.target_weight_kg <= self.weight_kg:
                raise ValueError("target weight must be above your current weight when your goal is to gain weight")
        if self.target_date is not None:
            if self.target_weight_kg is None:
                raise ValueError("add a target weight to use a target date")
            if not date.today() < self.target_date <= date.today().replace(year=date.today().year + 3):
                raise ValueError("target date must be in the future and within 3 years")
        if self.secondary_training_goal == self.training_goal:
            self.secondary_training_goal = None
        # Cardio schedule (when given) decides whether a cardio block goes into strength workouts.
        if self.cardio_schedule == "none":
            self.cardio_sessions_per_week, self.cardio_in_plan = 0, False
        elif self.cardio_schedule in ("strength_days", "mix"):
            self.cardio_in_plan = True
        elif self.cardio_schedule == "separate_days":
            self.cardio_in_plan = False
        if self.cardio_schedule not in (None, "none") and (self.cardio_sessions_per_week < 1 or not self.cardio_minutes):
            raise ValueError("choose how many days a week and how long each cardio session should be")
        if self.cardio_sessions_per_week == 0:
            self.cardio_in_plan = False
        if self.eating_pattern != "other":
            self.eating_pattern_other = None
        if self.cardio_in_plan and not self.cardio_minutes:
            raise ValueError("tell Venn how long your cardio sessions are to include them in your plan")
        return self


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sex: str | None
    birth_year: int | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goal: str | None
    goal_rate_pct: float
    protein_level: str
    diet_style: str
    dietary_preferences: list[str]
    training_goal: str | None
    experience: str | None
    days_per_week: int | None
    session_minutes: int | None
    equipment: list[str]
    preferred_split: str
    units: str
    secondary_training_goal: str | None = None
    cardio_sessions_per_week: int = 0
    cardio_minutes: int | None = None
    cardio_in_plan: bool = False
    goal_focus: str | None = None
    target_weight_kg: float | None = None
    target_date: date | None = None
    body_fat_pct: float | None = None
    height_unit: str = "cm"
    weight_unit: str = "kg"
    gym_location: str | None = None
    cardio_schedule: str | None = None
    eating_pattern: str | None = None
    eating_pattern_other: str | None = None
    exercise_ability: dict | None = None
    is_complete: bool = False
    goal_projection: dict | None = None


# ---------- targets ----------

class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method: str
    kcal: int
    protein_g: int
    carb_g: int
    fat_g: int
    breakdown: dict
    created_at: datetime


class ManualTargetIn(Strict):
    kcal: int = Field(ge=0, le=20000)
    protein_g: int = Field(ge=0, le=1000)
    carb_g: int = Field(ge=0, le=2000)
    fat_g: int = Field(ge=0, le=1000)


# ---------- limitations ----------

class LimitationIn(Strict):
    body_area: BodyArea
    kind: LimitationKind
    severity: LimitationSeverity = "caution"
    note: str = Field(default="", max_length=280)
    active: bool = True

    @field_validator("note")
    @classmethod
    def _note(cls, v: str) -> str:
        # Strip control characters: notes are user-written and will later reach the Training Agent.
        return "".join(ch for ch in v if ch.isprintable()).strip()


class LimitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body_area: str
    kind: str
    severity: str
    note: str
    active: bool
    created_at: datetime
    updated_at: datetime
