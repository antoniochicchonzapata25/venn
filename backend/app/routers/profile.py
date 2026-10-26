"""Profile/settings, nutrition targets, and self-reported training limitations.

Every query is filtered by the logged-in user's id. Ids in URLs are only ever
looked up together with that user id, so other users' rows return 404.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import NutritionTarget, Profile, TrainingLimitation, User
from app.schemas import (
    LimitationIn, LimitationOut, ManualTargetIn, ProfileIn, ProfileOut, TargetOut,
)
from app.security import current_user
from app.services import profiles
from app.services.targets import (
    DISCLAIMER, TargetInputError, calculate_targets, validate_manual_targets,
)
from app.services.goal_projection import PACE_RATES, projection
from app.vocab import DIETARY_PREFERENCES, EQUIPMENT

router = APIRouter(prefix="/api", tags=["profile"])


def _profile(db: Session, user: User) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def _profile_out(profile: Profile) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    out.is_complete = profiles.is_complete(profile)
    out.goal_projection = projection(profile.goal, profile.weight_kg, profile.goal_rate_pct or 0,
                                     profile.target_weight_kg, profile.target_date)
    return out


@router.get("/options")
def options() -> dict:
    """Choice lists for the settings form (public, no user data)."""
    return {"equipment": list(EQUIPMENT), "dietary_preferences": list(DIETARY_PREFERENCES), "disclaimer": DISCLAIMER,
            "pace_rates": PACE_RATES}


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)) -> ProfileOut:
    return _profile_out(_profile(db, user))


@router.put("/profile")
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    profile = _profile(db, user)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    try:
        new_target = profiles.refresh_formula_target(db, profile)
    except TargetInputError as error:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.errors) from error
    db.commit()
    return {
        "profile": _profile_out(profile),
        "target_updated": new_target is not None,
        "target": TargetOut.model_validate(new_target or profiles.current_target(db, user.id)),
    }


# ---------- targets ----------

@router.get("/targets/current")
def get_current_target(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    target = profiles.current_target(db, user.id)
    return {"target": TargetOut.model_validate(target) if target else None, "disclaimer": DISCLAIMER}


@router.get("/targets/preview")
def preview_target(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What the formula gives for the saved profile, without saving anything."""
    profile = _profile(db, user)
    if not profiles.is_complete(profile):
        raise HTTPException(status.HTTP_409_CONFLICT, "Complete your profile first.")
    try:
        result = calculate_targets(profiles.target_inputs(profile))
    except TargetInputError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.errors) from error
    return {
        "kcal": result.kcal, "protein_g": result.protein_g, "carb_g": result.carb_g, "fat_g": result.fat_g,
        "breakdown": result.breakdown(), "disclaimer": DISCLAIMER,
    }


@router.post("/targets/recalculate", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def recalculate(user: User = Depends(current_user), db: Session = Depends(get_db)) -> TargetOut:
    """Switch back to (or refresh) formula targets. Explicit user action."""
    profile = _profile(db, user)
    if not profiles.is_complete(profile):
        raise HTTPException(status.HTTP_409_CONFLICT, "Complete your profile first.")
    try:
        row = profiles.save_formula_target(db, user.id, calculate_targets(profiles.target_inputs(profile)))
    except TargetInputError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.errors) from error
    db.commit()
    return TargetOut.model_validate(row)


@router.post("/targets/manual", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def set_manual(body: ManualTargetIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> TargetOut:
    profile = _profile(db, user)
    errors = validate_manual_targets(body.kcal, body.protein_g, body.carb_g, body.fat_g, profile.sex, profile.weight_kg)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, errors)
    row = NutritionTarget(
        user_id=user.id, method="manual", **body.model_dump(),
        breakdown={"source": "entered by user", "macro_kcal": 4 * body.protein_g + 4 * body.carb_g + 9 * body.fat_g},
    )
    db.add(row)
    db.commit()
    return TargetOut.model_validate(row)


@router.get("/targets/history", response_model=list[TargetOut])
def target_history(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[TargetOut]:
    rows = db.scalars(
        select(NutritionTarget).where(NutritionTarget.user_id == user.id)
        .order_by(NutritionTarget.created_at.desc(), NutritionTarget.id.desc()).limit(50)
    )
    return [TargetOut.model_validate(r) for r in rows]


@router.get("/targets/{target_id}", response_model=TargetOut)
def get_target(target_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> TargetOut:
    row = db.scalar(select(NutritionTarget).where(NutritionTarget.id == target_id, NutritionTarget.user_id == user.id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target not found.")
    return TargetOut.model_validate(row)


# ---------- limitations ----------

def _own_limitation(db: Session, user: User, limitation_id: int) -> TrainingLimitation:
    row = db.scalar(select(TrainingLimitation).where(
        TrainingLimitation.id == limitation_id, TrainingLimitation.user_id == user.id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Limitation not found.")
    return row


@router.get("/limitations", response_model=list[LimitationOut])
def list_limitations(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[LimitationOut]:
    rows = db.scalars(select(TrainingLimitation).where(TrainingLimitation.user_id == user.id)
                      .order_by(TrainingLimitation.active.desc(), TrainingLimitation.created_at.desc()))
    return [LimitationOut.model_validate(r) for r in rows]


@router.post("/limitations", response_model=LimitationOut, status_code=status.HTTP_201_CREATED)
def add_limitation(body: LimitationIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> LimitationOut:
    count = len(db.scalars(select(TrainingLimitation.id).where(TrainingLimitation.user_id == user.id)).all())
    if count >= 20:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ["You can save at most 20 limitations."])
    row = TrainingLimitation(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    return LimitationOut.model_validate(row)


@router.put("/limitations/{limitation_id}", response_model=LimitationOut)
def update_limitation(limitation_id: int, body: LimitationIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> LimitationOut:
    row = _own_limitation(db, user, limitation_id)
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    db.commit()
    return LimitationOut.model_validate(row)


@router.delete("/limitations/{limitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_limitation(limitation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(_own_limitation(db, user, limitation_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
