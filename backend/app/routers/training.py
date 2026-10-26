"""Training: generate a workout, review it, swap exercises, log the session, and view history.

Generation and every replacement pass the deterministic rules in services/workout_rules.py.
All rows are filtered by the session user; other users' ids return 404. No AI calls here:
the generator is deterministic and works without an API key.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Profile, TrainingLimitation, User, Workout, WorkoutExercise, WorkoutSet
from app.security import current_user
from app.services import profiles
from app.services.exercises import SOURCE as EXERCISE_SOURCE
from app.services.exercises import catalog
from app.services.workout_generator import (
    DAY_NAMES, SPLITS, GenerationError, History, alternatives, choose_split, generate, next_day_type, weight_suggestion,
)
from app.services.workout_rules import (
    Limitation, TrainingContext, check_exercise, estimate_seconds, exercise_seconds, prescription, validate_plan,
)

router = APIRouter(prefix="/api/training", tags=["training"])
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
KG_PER_LB = 0.45359237
MAX_WEIGHT_KG = 500


# ---------------------------------------------------------------- schemas

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateIn(Strict):
    day_type: str | None = Field(default=None, max_length=16)
    split: str | None = Field(default=None, pattern="^(auto|full_body|upper_lower|push_pull_legs)$")
    minutes: int | None = Field(default=None, ge=15, le=180)
    variant: int = Field(default=0, ge=0, le=50)


class ReplaceIn(Strict):
    exercise_id: str = Field(max_length=80)


class SetIn(Strict):
    workout_exercise_id: int
    reps: int | None = Field(default=None, ge=0, le=100)
    weight: float | None = Field(default=None, ge=0)
    unit: str = Field(default="kg", pattern="^(kg|lb)$")
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)

    @model_validator(mode="after")
    def _weight(self) -> SetIn:
        if self.weight is not None and not math.isfinite(self.weight):
            raise ValueError("weight must be a number")
        if self.weight is not None and to_kg(self.weight, self.unit) > MAX_WEIGHT_KG:
            raise ValueError(f"weight above {MAX_WEIGHT_KG} kg ({round(MAX_WEIGHT_KG / KG_PER_LB)} lb) is not plausible")
        return self


class SetPatch(Strict):
    reps: int | None = Field(default=None, ge=0, le=100)
    weight: float | None = Field(default=None, ge=0)
    unit: str = Field(default="kg", pattern="^(kg|lb)$")
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)


class ExercisePatch(Strict):
    completed: bool


# ---------------------------------------------------------------- helpers

def to_kg(weight: float, unit: str) -> float:
    return round(weight * KG_PER_LB, 2) if unit == "lb" else round(weight, 2)


def to_lb(kg: float | None) -> float | None:
    return None if kg is None else round(kg / KG_PER_LB, 1)


def _utc(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


def _iso(dt: datetime | None) -> str | None:
    dt = _utc(dt)
    return None if dt is None else dt.isoformat().replace("+00:00", "Z")


def _context(db: Session, user: User, minutes: int | None = None) -> tuple[TrainingContext, Profile]:
    profile = db.get(Profile, user.id)
    if profile is None or not profiles.is_complete(profile):
        raise HTTPException(status.HTTP_409_CONFLICT, "Complete your profile (goal, experience, schedule, equipment) first.")
    lims = db.scalars(select(TrainingLimitation).where(TrainingLimitation.user_id == user.id, TrainingLimitation.active.is_(True)))
    ctx = TrainingContext(
        equipment=frozenset(profile.equipment or []),
        limitations=tuple(Limitation(l.body_area, l.severity, l.note) for l in lims),
        experience=profile.experience, goal=profile.training_goal,
        budget_minutes=minutes or profile.session_minutes,
        cardio_minutes=(profile.cardio_minutes or 0) if profile.cardio_in_plan else 0,
        cannot_do_yet=cannot_do_yet(profile.exercise_ability),
        secondary_goal=profile.secondary_training_goal,
    )
    return ctx, profile


ABILITY_EXERCISE_IDS = {
    "pushups": ("Pushups", "Push-Ups_-_Close_Triceps_Position"),
    "pullups": ("Pullups", "Chin-Up"),
    "dips": ("Bench_Dips",),
}


def cannot_do_yet(ability: dict | None) -> frozenset[str]:
    """Bodyweight exercises to leave out of generated workouts because the user can't do one rep yet."""
    ability = ability or {}
    return frozenset(i for k, ids in ABILITY_EXERCISE_IDS.items() if ability.get(k) == "none" for i in ids)


def _history(db: Session, user_id: int) -> History:
    h = History()
    workouts = db.scalars(select(Workout).where(Workout.user_id == user_id, Workout.status.in_(("completed", "planned", "in_progress")))
                          .options(selectinload(Workout.exercises).selectinload(WorkoutExercise.sets))
                          .order_by(Workout.finished_at.desc().nulls_last(), Workout.id.desc()))
    for w in workouts:
        if w.status == "completed":
            h.completed_by_split[w.split] = h.completed_by_split.get(w.split, 0) + 1
        for we in w.exercises:
            if we.replaced_exercise_id:
                h.swapped_in[we.exercise_id] = h.swapped_in.get(we.exercise_id, 0) + 1
                h.swapped_out[we.replaced_exercise_id] = h.swapped_out.get(we.replaced_exercise_id, 0) + 1
            if w.status == "completed" and we.sets and we.exercise_id not in h.last_sets:
                h.last_sets[we.exercise_id] = [(s.weight_kg, s.reps) for s in we.sets]
                if we.rep_high:
                    h.last_targets[we.exercise_id] = we.rep_high
    return h


def _own_workout(db: Session, user: User, workout_id: int) -> Workout:
    w = db.scalar(select(Workout).where(Workout.id == workout_id, Workout.user_id == user.id)
                  .options(selectinload(Workout.exercises).selectinload(WorkoutExercise.sets)))
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found.")
    return w


def _own_exercise(w: Workout, we_id: int) -> WorkoutExercise:
    we = next((e for e in w.exercises if e.id == we_id), None)
    if we is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found in this workout.")
    return we


def _rule_items(w: Workout) -> list[dict]:
    return [{"exercise_id": e.exercise_id, "sets": e.target_sets, "rep_high": e.rep_high,
             "target_seconds": e.target_seconds, "rest_s": e.rest_seconds} for e in w.exercises]


def _previous_best(db: Session, user_id: int, exercise_id: str, before_workout: int) -> float | None:
    rows = db.scalars(
        select(WorkoutSet.weight_kg).join(WorkoutExercise).join(Workout)
        .where(WorkoutSet.user_id == user_id, WorkoutExercise.exercise_id == exercise_id,
               Workout.status == "completed", Workout.id != before_workout, WorkoutSet.weight_kg.is_not(None)))
    return max(rows, default=None)


def _summary(db: Session, w: Workout) -> dict:
    sets = [s for e in w.exercises for s in e.sets]
    volume = sum((s.weight_kg or 0) * (s.reps or 0) for s in sets)
    planned_min = round(w.planned_seconds / 60)
    actual_min = round(w.actual_seconds / 60) if w.actual_seconds is not None else None
    records = []
    for e in w.exercises:
        top = max((s.weight_kg for s in e.sets if s.weight_kg), default=None)
        if top is None:
            continue
        prev = _previous_best(db, w.user_id, e.exercise_id, w.id)
        if prev is not None and top > prev:
            records.append({"exercise": e.name, "weight_kg": top, "previous_kg": prev})
    return {
        "planned_minutes": planned_min, "actual_minutes": actual_min,
        "difference_minutes": None if actual_min is None else actual_min - planned_min,
        "sets_logged": len(sets), "sets_planned": sum(e.target_sets for e in w.exercises),
        "exercises_completed": sum(1 for e in w.exercises if e.completed), "exercises_planned": len(w.exercises),
        "volume_kg": round(volume, 1), "records": records,
    }


def workout_out(db: Session, w: Workout, detail: bool = True) -> dict:
    out = {
        "id": w.id, "status": w.status, "name": w.name, "split": w.split, "day_type": w.day_type, "goal": w.goal,
        "objective": w.objective, "generator": w.generator, "budget_minutes": w.budget_minutes,
        "planned_minutes": round(w.planned_seconds / 60), "is_demo": w.is_demo,
        "created_at": _iso(w.created_at), "started_at": _iso(w.started_at), "finished_at": _iso(w.finished_at),
        "summary": _summary(db, w) if w.status == "completed" else None,
    }
    if not detail:
        return out
    out["explanation"] = w.explanation
    out["constraints"] = w.constraints
    out["exercises"] = [{
        "id": e.id, "position": e.position, "exercise_id": e.exercise_id, "name": e.name, "pattern": e.pattern,
        "role": e.role, "measure": e.measure, "target_sets": e.target_sets, "rep_low": e.rep_low, "rep_high": e.rep_high,
        "target_seconds": e.target_seconds, "rest_seconds": e.rest_seconds, "est_minutes": round(e.est_seconds / 60, 1),
        "instructions": e.instructions, "notes": e.notes, "suggested_weight_kg": e.suggested_weight_kg,
        "suggested_weight_lb": to_lb(e.suggested_weight_kg), "last_summary": e.last_summary,
        "replaced_exercise_id": e.replaced_exercise_id, "completed": e.completed,
        "equipment": list(catalog()[e.exercise_id].equipment) if e.exercise_id in catalog() else [],
        "sets": [{"id": s.id, "set_index": s.set_index, "reps": s.reps, "weight_kg": s.weight_kg,
                  "weight_lb": to_lb(s.weight_kg), "duration_seconds": s.duration_seconds, "logged_at": _iso(s.logged_at)}
                 for s in e.sets],
    } for e in w.exercises]
    out["exercise_source"] = EXERCISE_SOURCE
    return out


def _require(w: Workout, *statuses: str) -> None:
    if w.status not in statuses:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This workout is {w.status.replace('_', ' ')}.")


# ---------------------------------------------------------------- routes

@router.get("/options")
def training_options(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ctx, profile = _context(db, user)
    split, reason = choose_split(profile.preferred_split, profile.days_per_week)
    return {
        "split": split, "split_reason": reason, "day_types": [{"id": d, "name": DAY_NAMES[d]} for d in SPLITS[split]],
        "all_day_types": [{"id": d, "name": n} for d, n in DAY_NAMES.items()],
        "next_day_type": next_day_type(split, _history(db, user.id)), "session_minutes": profile.session_minutes,
        "units": profile.weight_unit or ("lb" if profile.units == "imperial" else "kg"),
        "preferred_split": profile.preferred_split,
        "weekly_plan": {"strength_days": profile.days_per_week, "cardio_schedule": profile.cardio_schedule,
                        "cardio_days": profile.cardio_sessions_per_week, "cardio_minutes": profile.cardio_minutes,
                        "cardio_in_workouts": bool(profile.cardio_in_plan)},
        "splits": [{"id": "auto", "name": "Automatic (by training days)"}, {"id": "full_body", "name": "Full body"},
                   {"id": "upper_lower", "name": "Upper / lower"}, {"id": "push_pull_legs", "name": "Push / pull / legs"}],
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_workout(body: GenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ctx, profile = _context(db, user, body.minutes)
    if body.split is not None and body.split != profile.preferred_split:
        profile.preferred_split = body.split  # the user changed their split in Training: keep it as the default
        if body.day_type is not None and body.split != "auto" and body.day_type not in SPLITS[body.split]:
            body.day_type = None
    try:
        plan = generate(ctx=ctx, preferred_split=profile.preferred_split, days_per_week=profile.days_per_week,
                        history=_history(db, user.id), day_type=body.day_type, variant=body.variant)
    except GenerationError as error:
        raise HTTPException(UNPROCESSABLE, {"code": "cannot_generate", "message": error.message,
                                            "alternatives": error.alternatives}) from error
    # A new plan replaces any earlier plan that was never started.
    for old in db.scalars(select(Workout).where(Workout.user_id == user.id, Workout.status == "planned")):
        old.status = "discarded"
    w = Workout(
        user_id=user.id, status="planned", name=plan.name, split=plan.split, day_type=plan.day_type, goal=ctx.goal,
        objective=plan.objective, explanation=plan.explanation, generator=plan.generator, budget_minutes=ctx.budget_minutes,
        planned_seconds=plan.est_seconds,
        constraints={"equipment": sorted(ctx.equipment), "experience": ctx.experience,
                     "limitations": [{"body_area": l.body_area, "severity": l.severity} for l in ctx.limitations]},
    )
    for pos, it in enumerate(plan.items):
        w.exercises.append(WorkoutExercise(
            user_id=user.id, position=pos, exercise_id=it.exercise.id, name=it.exercise.name, pattern=it.exercise.pattern,
            slot_patterns=list(it.slot_patterns), role=it.role, measure=it.exercise.measure, target_sets=it.sets,
            rep_low=it.rep_low, rep_high=it.rep_high, target_seconds=it.target_seconds, rest_seconds=it.rest_s,
            est_seconds=it.est_seconds, instructions=list(it.exercise.instructions), notes=it.notes,
            suggested_weight_kg=it.suggested_weight_kg, last_summary=it.last_summary))
    db.add(w)
    db.commit()
    return workout_out(db, _own_workout(db, user, w.id))


@router.get("/workouts")
def list_workouts(status_filter: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    q = select(Workout).where(Workout.user_id == user.id, Workout.status != "discarded")
    if status_filter:
        q = q.where(Workout.status == status_filter)
    rows = db.scalars(q.options(selectinload(Workout.exercises).selectinload(WorkoutExercise.sets))
                      .order_by(Workout.created_at.desc(), Workout.id.desc()).limit(50))
    return {"workouts": [workout_out(db, w, detail=False) for w in rows]}


@router.get("/summary")
def training_summary(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    profile = db.get(Profile, user.id)
    rows = list(db.scalars(select(Workout).where(Workout.user_id == user.id, Workout.status.in_(("planned", "in_progress", "completed")))
                           .options(selectinload(Workout.exercises).selectinload(WorkoutExercise.sets))
                           .order_by(Workout.created_at.desc(), Workout.id.desc())))
    week_ago = datetime.now(UTC) - timedelta(days=7)
    completed = [w for w in rows if w.status == "completed"]
    completed.sort(key=lambda w: _utc(w.finished_at), reverse=True)
    recent = completed[:5]
    diffs = [round(w.actual_seconds / 60) - round(w.planned_seconds / 60) for w in recent if w.actual_seconds is not None]
    return {
        "planned": next((workout_out(db, w, detail=False) for w in rows if w.status == "planned"), None),
        "in_progress": next((workout_out(db, w, detail=False) for w in rows if w.status == "in_progress"), None),
        "completed_last_7_days": sum(1 for w in completed if _utc(w.finished_at) >= week_ago),
        "days_per_week": profile.days_per_week if profile else None,
        "history": [workout_out(db, w, detail=False) for w in completed[:10]],
        "average_difference_minutes": round(sum(diffs) / len(diffs), 1) if diffs else None,
        "sessions_compared": len(diffs),
    }


@router.get("/workouts/{workout_id}")
def get_workout(workout_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return workout_out(db, _own_workout(db, user, workout_id))


@router.delete("/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_workout(workout_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    w = _own_workout(db, user, workout_id)
    _require(w, "planned", "in_progress")
    w.status = "discarded"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workouts/{workout_id}/exercises/{we_id}/alternatives")
def exercise_alternatives(workout_id: int, we_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    we = _own_exercise(w, we_id)
    ctx, _ = _context(db, user, w.budget_minutes)
    current = catalog()[we.exercise_id]
    used = {e.exercise_id for e in w.exercises}
    options = alternatives(current, ctx, used, tuple(we.slot_patterns))
    return {"exercise": we.name, "alternatives": [
        {**o["exercise"].summary(), "reason": o["reason"], "notes": o["notes"]} for o in options],
        "message": None if options else "No other exercise fits this slot with your equipment and reported limitations."}


@router.post("/workouts/{workout_id}/exercises/{we_id}/replace")
def replace_exercise(workout_id: int, we_id: int, body: ReplaceIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "planned", "in_progress")
    we = _own_exercise(w, we_id)
    if we.sets:
        raise HTTPException(status.HTTP_409_CONFLICT, "Sets are already logged for this exercise; it can't be replaced.")
    new = catalog().get(body.exercise_id)
    if new is None:
        raise HTTPException(UNPROCESSABLE, ["Unknown exercise."])
    if new.id in {e.exercise_id for e in w.exercises}:
        raise HTTPException(UNPROCESSABLE, [f"{new.name} is already in this workout."])
    ctx, _ = _context(db, user, w.budget_minutes)
    check = check_exercise(new, ctx, enforce_level=False)
    if not check.ok:  # backend rule: nothing incompatible gets in, whatever the client sends
        raise HTTPException(UNPROCESSABLE, [f"{new.name} {r}." for r in check.reasons])
    rx = prescription(w.goal, we.role, ctx.experience, new)
    original = we.replaced_exercise_id or we.exercise_id
    we.replaced_exercise_id = None if new.id == original else original
    we.exercise_id, we.name, we.pattern, we.measure = new.id, new.name, new.pattern, new.measure
    we.target_sets, we.rep_low, we.rep_high, we.target_seconds = rx["sets"], rx["rep_low"], rx["rep_high"], rx["target_seconds"]
    we.rest_seconds, we.instructions, we.notes = rx["rest_s"], list(new.instructions), check.notes
    we.suggested_weight_kg, we.last_summary = weight_suggestion(new, _history(db, user.id))
    we.est_seconds = exercise_seconds(new, we.target_sets, we.rep_high, we.target_seconds, we.rest_seconds)
    if w.status == "planned":
        w.planned_seconds = estimate_seconds(_rule_items(w))
    db.commit()
    out = workout_out(db, _own_workout(db, user, w.id))
    over = validate_plan(_rule_items(w), ctx)
    out["warnings"] = [v for v in over if "budget" in v]
    return out


@router.post("/workouts/{workout_id}/start")
def start_workout(workout_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "planned")
    active = db.scalar(select(Workout).where(Workout.user_id == user.id, Workout.status == "in_progress"))
    if active is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another workout is already in progress. Finish or discard it first.")
    w.status, w.started_at = "in_progress", datetime.now(UTC)
    db.commit()
    return workout_out(db, w)


@router.post("/workouts/{workout_id}/sets", status_code=status.HTTP_201_CREATED)
def log_set(workout_id: int, body: SetIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "in_progress")
    we = _own_exercise(w, body.workout_exercise_id)
    if we.measure == "time" and body.duration_seconds is None:
        raise HTTPException(UNPROCESSABLE, ["Enter how many seconds you held it."])
    if we.measure == "reps" and body.reps is None:
        raise HTTPException(UNPROCESSABLE, ["Enter the number of reps."])
    s = WorkoutSet(workout_exercise_id=we.id, user_id=user.id, set_index=len(we.sets) + 1, reps=body.reps,
                   weight_kg=None if body.weight is None else to_kg(body.weight, body.unit),
                   duration_seconds=body.duration_seconds)
    we.sets.append(s)
    if len(we.sets) >= we.target_sets:
        we.completed = True
    db.commit()
    return workout_out(db, w)


@router.patch("/workouts/{workout_id}/sets/{set_id}")
def edit_set(workout_id: int, set_id: int, body: SetPatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "in_progress")
    s = next((s for e in w.exercises for s in e.sets if s.id == set_id), None)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set not found.")
    if body.weight is not None and to_kg(body.weight, body.unit) > MAX_WEIGHT_KG:
        raise HTTPException(UNPROCESSABLE, [f"weight above {MAX_WEIGHT_KG} kg is not plausible"])
    if body.reps is not None:
        s.reps = body.reps
    if body.weight is not None:
        s.weight_kg = to_kg(body.weight, body.unit)
    if body.duration_seconds is not None:
        s.duration_seconds = body.duration_seconds
    db.commit()
    return workout_out(db, w)


@router.delete("/workouts/{workout_id}/sets/{set_id}")
def delete_set(workout_id: int, set_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "in_progress")
    for e in w.exercises:
        for s in e.sets:
            if s.id == set_id:
                e.sets.remove(s)
                for n, rest in enumerate(e.sets, start=1):
                    rest.set_index = n
                e.completed = len(e.sets) >= e.target_sets
                db.commit()
                return workout_out(db, w)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Set not found.")


@router.patch("/workouts/{workout_id}/exercises/{we_id}")
def mark_exercise(workout_id: int, we_id: int, body: ExercisePatch, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "in_progress")
    _own_exercise(w, we_id).completed = body.completed
    db.commit()
    return workout_out(db, w)


@router.post("/workouts/{workout_id}/finish")
def finish_workout(workout_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    w = _own_workout(db, user, workout_id)
    _require(w, "in_progress")
    if not any(e.sets for e in w.exercises):
        raise HTTPException(UNPROCESSABLE, ["Log at least one set before finishing, or discard the workout."])
    w.finished_at = datetime.now(UTC)
    w.actual_seconds = max(0, int((w.finished_at - _utc(w.started_at)).total_seconds()))
    w.status = "completed"
    db.commit()
    return workout_out(db, w)
