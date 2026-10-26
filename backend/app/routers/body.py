"""Body: weight and measurement history, estimated muscle recovery, and user-reported soreness.

Everything is filtered by the session user; other users' ids return 404. Values are stored in metric
(kg, cm) and converted from the unit the client sends. No AI calls: all numbers are deterministic.
Venn does not infer body-fat percentage or attribute weight changes to fat or muscle.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import BodyMeasurement, BodyWeight, SorenessRating, User, Workout, WorkoutExercise
from app.security import current_user
from app.services import recovery

router = APIRouter(prefix="/api/body", tags=["body"])
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
KG_PER_LB = 0.45359237
CM_PER_IN = 2.54
EARLIEST_DATE = date(2000, 1, 1)

# Plausible adult ranges (kg / cm). Values outside are rejected as likely typos.
WEIGHT_RANGE_KG = (25.0, 350.0)
MEASUREMENT_RANGES_CM = {
    "waist": (40.0, 250.0), "chest": (50.0, 250.0), "hips": (50.0, 250.0), "biceps": (15.0, 80.0), "thigh": (25.0, 120.0),
}
MEASUREMENT_FIELDS = tuple(MEASUREMENT_RANGES_CM)
NOTE = ("Recorded values only. Weight changes can reflect water, food in the gut and measurement timing as well as "
        "fat or muscle; Venn does not estimate body fat from these entries.")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_date(d: date) -> date:
    if d < EARLIEST_DATE:
        raise ValueError(f"Pick a date on or after {EARLIEST_DATE.isoformat()}.")
    if d > datetime.now(UTC).date() + timedelta(days=1):
        raise ValueError("The date can't be in the future.")
    return d


class WeightIn(Strict):
    entry_date: date
    weight: float = Field(gt=0, le=1000)
    unit: str = Field(default="kg", pattern="^(kg|lb)$")

    _date = field_validator("entry_date")(_check_date)


class MeasurementIn(Strict):
    entry_date: date
    unit: str = Field(default="cm", pattern="^(cm|in)$")
    waist: float | None = Field(default=None, gt=0, le=1000)
    chest: float | None = Field(default=None, gt=0, le=1000)
    hips: float | None = Field(default=None, gt=0, le=1000)
    biceps: float | None = Field(default=None, gt=0, le=1000)
    thigh: float | None = Field(default=None, gt=0, le=1000)

    _date = field_validator("entry_date")(_check_date)


class SorenessIn(Strict):
    rating: int = Field(ge=0, le=10)


# ---------------------------------------------------------------- weight

def _weight_out(w: BodyWeight) -> dict:
    return {"id": w.id, "entry_date": w.entry_date.isoformat(), "weight_kg": round(w.weight_kg, 2)}


def weight_history(db: Session, user_id: int) -> dict:
    rows = list(db.scalars(select(BodyWeight).where(BodyWeight.user_id == user_id)
                           .order_by(BodyWeight.entry_date.desc(), BodyWeight.id.desc())))
    latest = rows[0] if rows else None
    previous = rows[1] if len(rows) > 1 else None
    change = round(latest.weight_kg - previous.weight_kg, 2) if latest and previous else None
    return {
        "entries": [_weight_out(w) for w in rows],
        "latest": _weight_out(latest) if latest else None,
        "previous": _weight_out(previous) if previous else None,
        "change_kg": change,
        "days_between": (latest.entry_date - previous.entry_date).days if latest and previous else None,
        "note": NOTE,
    }


@router.get("/weights")
def list_weights(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return weight_history(db, user.id)


@router.post("/weights", status_code=status.HTTP_201_CREATED)
def add_weight(body: WeightIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    kg = body.weight * KG_PER_LB if body.unit == "lb" else body.weight
    lo, hi = WEIGHT_RANGE_KG
    if not lo <= kg <= hi:
        shown = (f"{lo / KG_PER_LB:.0f}-{hi / KG_PER_LB:.0f} lb" if body.unit == "lb" else f"{lo:.0f}-{hi:.0f} kg")
        raise HTTPException(UNPROCESSABLE, [f"{body.weight:g} {body.unit} looks implausible. Enter a body weight between {shown}."])
    existing = db.scalar(select(BodyWeight).where(BodyWeight.user_id == user.id, BodyWeight.entry_date == body.entry_date))
    if existing:  # one weight per date: a new value for the same date replaces it
        existing.weight_kg = kg
    else:
        db.add(BodyWeight(user_id=user.id, entry_date=body.entry_date, weight_kg=kg))
    db.commit()
    return {**weight_history(db, user.id), "replaced": existing is not None}


@router.delete("/weights/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weight(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(BodyWeight, entry_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Weight entry not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- measurements

def _measurement_out(m: BodyMeasurement) -> dict:
    return {"id": m.id, "entry_date": m.entry_date.isoformat(),
            **{f"{f}_cm": (round(v, 1) if (v := getattr(m, f"{f}_cm")) is not None else None) for f in MEASUREMENT_FIELDS}}


def measurement_history(db: Session, user_id: int) -> dict:
    rows = list(db.scalars(select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)
                           .order_by(BodyMeasurement.entry_date.desc(), BodyMeasurement.id.desc())))
    entries = [_measurement_out(m) for m in rows]
    # Per field: the latest recorded value vs. the next earlier entry that recorded the same field.
    comparison = {}
    for f in MEASUREMENT_FIELDS:
        recorded = [e for e in entries if e[f"{f}_cm"] is not None]
        latest, previous = (recorded + [None, None])[:2]
        comparison[f] = {
            "latest_cm": latest[f"{f}_cm"] if latest else None, "latest_date": latest["entry_date"] if latest else None,
            "previous_cm": previous[f"{f}_cm"] if previous else None, "previous_date": previous["entry_date"] if previous else None,
            "change_cm": round(latest[f"{f}_cm"] - previous[f"{f}_cm"], 1) if latest and previous else None,
        }
    return {"entries": entries, "comparison": comparison, "fields": list(MEASUREMENT_FIELDS), "note": NOTE}


@router.get("/measurements")
def list_measurements(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return measurement_history(db, user.id)


@router.post("/measurements", status_code=status.HTTP_201_CREATED)
def add_measurement(body: MeasurementIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    factor = CM_PER_IN if body.unit == "in" else 1.0
    values: dict[str, float | None] = {}
    errors = []
    for f, (lo, hi) in MEASUREMENT_RANGES_CM.items():
        raw = getattr(body, f)
        if raw is None:
            values[f"{f}_cm"] = None
            continue
        cm = raw * factor
        if not lo <= cm <= hi:
            shown = f"{lo / CM_PER_IN:.0f}-{hi / CM_PER_IN:.0f} in" if body.unit == "in" else f"{lo:.0f}-{hi:.0f} cm"
            errors.append(f"{f.capitalize()}: {raw:g} {body.unit} looks implausible (expected {shown}).")
        values[f"{f}_cm"] = cm
    if all(v is None for v in values.values()):
        errors.append("Enter at least one measurement.")
    if errors:
        raise HTTPException(UNPROCESSABLE, errors)
    existing = db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user.id,
                                                       BodyMeasurement.entry_date == body.entry_date))
    if existing:  # one entry per date: a new entry for the same date replaces all its values
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        db.add(BodyMeasurement(user_id=user.id, entry_date=body.entry_date, **values))
    db.commit()
    return {**measurement_history(db, user.id), "replaced": existing is not None}


@router.delete("/measurements/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(BodyMeasurement, entry_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measurement entry not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- recovery

def completed_workouts(db: Session, user_id: int, since: datetime) -> list[recovery.CompletedWorkout]:
    rows = db.scalars(select(Workout).where(Workout.user_id == user_id, Workout.status == "completed",
                                            Workout.finished_at.is_not(None))
                      .order_by(Workout.finished_at.desc()).limit(200)
                      .options(selectinload(Workout.exercises).selectinload(WorkoutExercise.sets)))
    rows = [w for w in rows if _aware(w.finished_at) >= since]
    return [
        recovery.CompletedWorkout(
            id=w.id, name=w.name, finished_at=w.finished_at, is_demo=w.is_demo,
            exercises=[recovery.LoggedExercise(
                exercise_id=e.exercise_id, name=e.name,
                sets=sum(1 for s in e.sets if (s.reps or 0) > 0 or (s.duration_seconds or 0) > 0)) for e in w.exercises])
        for w in rows
    ]


@router.get("/recovery")
def get_recovery(tz_offset: int | None = Query(default=None, ge=-900, le=900),
                 user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    now = datetime.now(UTC)
    result = recovery.estimate(completed_workouts(db, user.id, now - timedelta(days=90)), now, tz_offset)
    ratings = db.scalars(select(SorenessRating).where(SorenessRating.user_id == user.id))
    result["soreness"] = {r.muscle_group: {"rating": r.rating, "recorded_at": _iso(r.recorded_at)} for r in ratings}
    return result


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return _aware(dt).isoformat()


# ---------------------------------------------------------------- user-reported soreness (separate from the estimate)

def _group(group: str) -> str:
    if group not in recovery.GROUPS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown muscle group.")
    return group


@router.put("/soreness/{group}")
def set_soreness(group: str, body: SorenessIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    group = _group(group)
    row = db.scalar(select(SorenessRating).where(SorenessRating.user_id == user.id, SorenessRating.muscle_group == group))
    if row is None:
        row = SorenessRating(user_id=user.id, muscle_group=group, rating=body.rating)
        db.add(row)
    else:
        row.rating = body.rating
        row.recorded_at = datetime.now(UTC)
    db.commit()
    return {"muscle_group": group, "rating": row.rating, "recorded_at": _iso(row.recorded_at)}


@router.delete("/soreness/{group}", status_code=status.HTTP_204_NO_CONTENT)
def delete_soreness(group: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    group = _group(group)
    row = db.scalar(select(SorenessRating).where(SorenessRating.user_id == user.id, SorenessRating.muscle_group == group))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No soreness rating recorded for this muscle group.")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
