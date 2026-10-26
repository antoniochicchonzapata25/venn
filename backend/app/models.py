"""Database tables for Milestone 1.

Every user-owned table has a non-null `user_id` foreign key. Route handlers
only ever query these tables through `user_id` taken from the login session.
"""

from __future__ import annotations

from datetime import UTC, datetime

from datetime import date as Date

from sqlalchemy import JSON, Boolean, Date as SqlDate, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[Profile] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserSession(Base):
    """Login sessions. Only a SHA-256 hash of the cookie token is stored."""

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Profile(Base):
    """Body stats, goals and training preferences. Nullable until onboarding is done."""

    __tablename__ = "profile"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    # Body and nutrition goal
    sex: Mapped[str | None] = mapped_column(String(16))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    activity_level: Mapped[str | None] = mapped_column(String(16))
    goal: Mapped[str | None] = mapped_column(String(16))
    goal_rate_pct: Mapped[float] = mapped_column(Float, default=0.0)
    protein_level: Mapped[str] = mapped_column(String(16), default="standard")
    diet_style: Mapped[str] = mapped_column(String(16), default="balanced")
    dietary_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Training
    training_goal: Mapped[str | None] = mapped_column(String(24))
    experience: Mapped[str | None] = mapped_column(String(16))
    days_per_week: Mapped[int | None] = mapped_column(Integer)
    session_minutes: Mapped[int | None] = mapped_column(Integer)
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_split: Mapped[str] = mapped_column(String(24), default="auto")
    secondary_training_goal: Mapped[str | None] = mapped_column(String(24))
    cardio_sessions_per_week: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cardio_minutes: Mapped[int | None] = mapped_column(Integer)
    cardio_in_plan: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Goal details (Milestone 3.5). goal + goal_rate_pct still drive the calorie formula.
    goal_focus: Mapped[str | None] = mapped_column(String(16))
    target_weight_kg: Mapped[float | None] = mapped_column(Float)
    target_date: Mapped[Date | None] = mapped_column(SqlDate)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    # Milestone 3.6
    gym_location: Mapped[str | None] = mapped_column(String(20))
    cardio_schedule: Mapped[str | None] = mapped_column(String(16))
    eating_pattern: Mapped[str | None] = mapped_column(String(16))
    eating_pattern_other: Mapped[str | None] = mapped_column(String(120))
    exercise_ability: Mapped[dict | None] = mapped_column(JSON)
    # Display
    units: Mapped[str] = mapped_column(String(10), default="metric")  # legacy; mirrors weight_unit
    height_unit: Mapped[str] = mapped_column(String(8), default="cm", server_default="cm")
    weight_unit: Mapped[str] = mapped_column(String(4), default="kg", server_default="kg")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class NutritionTarget(Base):
    """Versioned daily targets. The newest row is the current target."""

    __tablename__ = "nutrition_target"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(16))  # "formula" | "manual"
    kcal: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[int] = mapped_column(Integer)
    carb_g: Mapped[int] = mapped_column(Integer)
    fat_g: Mapped[int] = mapped_column(Integer)
    # Formula inputs and intermediate values, so every target is explainable later.
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class TrainingLimitation(Base):
    """A restriction the user reported themselves. Venn never infers or diagnoses these."""

    __tablename__ = "training_limitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    body_area: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(16))  # "temporary" | "ongoing"
    severity: Mapped[str] = mapped_column(String(16))  # "avoid" | "caution"
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AiUsage(Base):
    """One row per model call: real token counts from the API response (evidence for tokenomics)."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(40))
    served_model: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Milestone 4: link to the agent run, and whether the provider reported usage at all
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_run.id", ondelete="CASCADE"), index=True)
    usage_reported: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)


# ---------------------------------------------------------------- nutrition (Milestone 2)

class AppMeta(Base):
    """Small key/value table (e.g. which bundled food-catalog version is loaded)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Food(Base):
    """A food from the bundled catalog. Values are per 100 g (or per 100 ml when basis == 'ml')."""

    __tablename__ = "food"
    __table_args__ = (UniqueConstraint("source", "source_ref", name="uq_food_source_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(24))  # "usda_sr_legacy" | "usda_branded"
    source_ref: Mapped[str] = mapped_column(String(32))  # FoodData Central fdc_id
    name: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(160), default="")
    barcode: Mapped[str | None] = mapped_column(String(14), unique=True, index=True)  # GTIN-14, zero-padded
    basis: Mapped[str] = mapped_column(String(2), default="g")  # "g" | "ml"
    kcal_100: Mapped[float] = mapped_column(Float)
    protein_100: Mapped[float] = mapped_column(Float)
    carb_100: Mapped[float] = mapped_column(Float)
    fat_100: Mapped[float] = mapped_column(Float)
    serving_size: Mapped[float | None] = mapped_column(Float)  # in basis units (branded label serving)
    serving_label: Mapped[str] = mapped_column(String(120), default="")
    published: Mapped[str] = mapped_column(String(20), default="")

    portions: Mapped[list[FoodPortion]] = relationship(
        back_populates="food", cascade="all, delete-orphan", order_by="FoodPortion.seq")


class FoodPortion(Base):
    """A household measure for a food, e.g. '1 cup, chopped' = 140 g."""

    __tablename__ = "food_portion"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("food.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(160))
    amount: Mapped[float] = mapped_column(Float)  # grams (or ml) for one of this portion

    food: Mapped[Food] = relationship(back_populates="portions")


class FoodEntry(Base):
    """One logged food. Nutrition is computed and stored when logged, so later catalog
    updates never rewrite history. `nutrition_basis` keeps the per-100 values and unit
    sizes used, so edits recompute from the same snapshot."""

    __tablename__ = "food_entry"
    __table_args__ = (Index("ix_food_entry_user_date", "user_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("food.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # "catalog" | "manual"
    description: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str] = mapped_column(String(160), default="")
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    unit_label: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float | None] = mapped_column(Float)  # grams or ml eaten (None for manual entries)
    nutrition_basis: Mapped[dict] = mapped_column(JSON)
    kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carb_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    # The user's local wall-clock time of eating (no time zone), and its date for day views.
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    local_date: Mapped[Date] = mapped_column(SqlDate)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- training (Milestone 3)

class Workout(Base):
    """A generated routine and, once performed, its logged session.
    status: planned -> in_progress -> completed (or discarded)."""

    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    name: Mapped[str] = mapped_column(String(80))
    split: Mapped[str] = mapped_column(String(24))
    day_type: Mapped[str] = mapped_column(String(16))
    goal: Mapped[str] = mapped_column(String(24))
    objective: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[list] = mapped_column(JSON, default=list)
    generator: Mapped[str] = mapped_column(String(40))
    budget_minutes: Mapped[int] = mapped_column(Integer)
    planned_seconds: Mapped[int] = mapped_column(Integer)  # estimate when generated (updated by swaps before start)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)  # equipment + limitations used, for traceability
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_seconds: Mapped[int | None] = mapped_column(Integer)

    exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="workout", cascade="all, delete-orphan", order_by="WorkoutExercise.position")


class WorkoutExercise(Base):
    """One exercise in a workout: the plan (targets) plus a snapshot of the catalog entry."""

    __tablename__ = "workout_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workout.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    exercise_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    pattern: Mapped[str] = mapped_column(String(24))
    slot_patterns: Mapped[list] = mapped_column(JSON, default=list)
    role: Mapped[str] = mapped_column(String(12))
    measure: Mapped[str] = mapped_column(String(8))
    target_sets: Mapped[int] = mapped_column(Integer)
    rep_low: Mapped[int | None] = mapped_column(Integer)
    rep_high: Mapped[int | None] = mapped_column(Integer)
    target_seconds: Mapped[int | None] = mapped_column(Integer)
    rest_seconds: Mapped[int] = mapped_column(Integer)
    est_seconds: Mapped[int] = mapped_column(Integer)
    instructions: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    suggested_weight_kg: Mapped[float | None] = mapped_column(Float)
    last_summary: Mapped[str | None] = mapped_column(String(200))
    replaced_exercise_id: Mapped[str | None] = mapped_column(String(80))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    workout: Mapped[Workout] = relationship(back_populates="exercises")
    sets: Mapped[list[WorkoutSet]] = relationship(
        back_populates="workout_exercise", cascade="all, delete-orphan", order_by="WorkoutSet.set_index")


class WorkoutSet(Base):
    """One logged set. Weight is stored in kg; the UI converts to lb if the user prefers."""

    __tablename__ = "workout_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercise.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    set_index: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")


# ---------------------------------------------------------------- AI Coach (Milestone 4)

class AgentRun(Base):
    """One AI Coach request: routing, tool calls, model calls, checks and the final answer (the run trace)."""

    __tablename__ = "agent_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(String(500))
    workflow: Mapped[str] = mapped_column(String(16))
    routed_by: Mapped[str] = mapped_column(String(16))  # "keywords" | "model" | "user"
    status: Mapped[str] = mapped_column(String(16))  # "ok" | "error" | "limit" | "disabled"
    answer: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(300))
    trace: Mapped[list] = mapped_column(JSON, default=list)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(40))
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usage_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ---------------------------------------------------------------- Body (Milestone 5)

class BodyWeight(Base):
    """One self-recorded body weight per user per date. Stored in kg; shown in the user's unit."""

    __tablename__ = "body_weight"
    __table_args__ = (UniqueConstraint("user_id", "entry_date", name="uq_body_weight_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    entry_date: Mapped[Date] = mapped_column(SqlDate)
    weight_kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BodyMeasurement(Base):
    """Self-recorded circumferences for one date, in cm. Any field may be missing (not measured)."""

    __tablename__ = "body_measurement"
    __table_args__ = (UniqueConstraint("user_id", "entry_date", name="uq_body_measurement_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    entry_date: Mapped[Date] = mapped_column(SqlDate)
    waist_cm: Mapped[float | None] = mapped_column(Float)
    chest_cm: Mapped[float | None] = mapped_column(Float)
    hips_cm: Mapped[float | None] = mapped_column(Float)
    biceps_cm: Mapped[float | None] = mapped_column(Float)
    thigh_cm: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SorenessRating(Base):
    """User-reported soreness (0-10) for one muscle group; the latest rating replaces the previous one.
    Kept separate from the workout-history recovery estimate."""

    __tablename__ = "soreness_rating"
    __table_args__ = (UniqueConstraint("user_id", "muscle_group", name="uq_soreness_user_group"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    muscle_group: Mapped[str] = mapped_column(String(16))
    rating: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
