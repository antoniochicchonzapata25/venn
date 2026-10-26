"""Profile helpers and target versioning. All functions take the owning user's id explicitly."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NutritionTarget, Profile
from app.services.targets import TargetInputs, TargetResult, calculate_targets

REQUIRED_FIELDS = (
    "sex", "birth_year", "height_cm", "weight_kg", "activity_level", "goal",
    "training_goal", "experience", "days_per_week", "session_minutes",
)


def is_complete(profile: Profile) -> bool:
    return all(getattr(profile, f) is not None for f in REQUIRED_FIELDS)


def target_inputs(profile: Profile, today: date | None = None) -> TargetInputs:
    today = today or date.today()
    return TargetInputs(
        sex=profile.sex, age=today.year - profile.birth_year,
        height_cm=profile.height_cm, weight_kg=profile.weight_kg,
        activity_level=profile.activity_level, goal=profile.goal,
        goal_rate_pct=profile.goal_rate_pct, protein_level=profile.protein_level,
        diet_style=profile.diet_style, target_weight_kg=profile.target_weight_kg,
    )


def current_target(db: Session, user_id: int) -> NutritionTarget | None:
    return db.scalar(
        select(NutritionTarget)
        .where(NutritionTarget.user_id == user_id)
        .order_by(NutritionTarget.created_at.desc(), NutritionTarget.id.desc())
        .limit(1)
    )


def save_formula_target(db: Session, user_id: int, result: TargetResult) -> NutritionTarget:
    row = NutritionTarget(
        user_id=user_id, method="formula",
        kcal=result.kcal, protein_g=result.protein_g, carb_g=result.carb_g, fat_g=result.fat_g,
        breakdown=result.breakdown(),
    )
    db.add(row)
    return row


def refresh_formula_target(db: Session, profile: Profile) -> NutritionTarget | None:
    """After a profile change, add a new formula target unless the user chose manual targets."""
    latest = current_target(db, profile.user_id)
    if latest is not None and latest.method == "manual":
        return None
    return save_formula_target(db, profile.user_id, calculate_targets(target_inputs(profile)))
