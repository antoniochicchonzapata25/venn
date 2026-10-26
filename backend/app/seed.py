"""Demo data. Idempotent: running it twice does not duplicate anything."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Food, FoodEntry, NutritionTarget, Profile, TrainingLimitation, User, Workout, WorkoutExercise, WorkoutSet
from app.services import nutrition
from app.security import hash_password
from app.services.profiles import refresh_formula_target

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "venn-demo-2026"  # documented in the README; demo account only


def ensure_demo_user(db: Session) -> tuple[User, bool]:
    """Create the demo user if missing. Returns (user, created)."""
    user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
    if user is not None:
        return user, False
    user = User(username=DEMO_USERNAME, display_name="Demo Athlete", password_hash=hash_password(DEMO_PASSWORD))
    user.profile = Profile(
        sex="male", birth_year=date.today().year - 30, height_cm=178, weight_kg=82,
        activity_level="moderate", goal="lose", goal_rate_pct=0.5, protein_level="high", diet_style="balanced",
        dietary_preferences=[], training_goal="build_muscle", experience="intermediate",
        days_per_week=4, session_minutes=75, preferred_split="upper_lower",
        equipment=["barbell", "dumbbell", "cable", "machine", "bench", "pull-up bar", "body only"], units="metric",
    )
    db.add(user)
    db.flush()
    db.add(TrainingLimitation(
        user_id=user.id, body_area="lower_back", kind="ongoing", severity="caution",
        note="Reported by user: lower-back issue; keep heavy spinal loading moderate.",
    ))
    refresh_formula_target(db, user.profile)
    db.commit()
    return user, True


# (days ago, "HH:MM", food name or barcode, quantity, unit or portion-label prefix)
DEMO_MEALS = [
    (0, "07:45", "Cereals, oats, regular and quick, not fortified, dry", 50, "g"),
    (0, "07:45", "Milk, reduced fat, fluid, 2% milkfat, with added vitamin A and vitamin D", 1, "1 cup"),
    (0, "07:50", "Bananas, raw", 118, "g"),
    (0, "12:40", "Chicken, broilers or fryers, breast, meat only, cooked, roasted", 150, "g"),
    (0, "12:40", "Rice, white, long-grain, regular, enriched, cooked", 1, "1 cup"),
    (0, "12:40", "Broccoli, cooked, boiled, drained, without salt", 100, "g"),
    (0, "16:15", "850004694039", 1, "serving"),
    (1, "08:10", "Egg, whole, cooked, scrambled", 2, "1 large"),
    (1, "08:10", "Bread, whole-wheat, commercially prepared", 2, "1 slice"),
    (1, "13:05", "Chicken, broilers or fryers, breast, meat only, cooked, roasted", 200, "g"),
    (1, "13:05", "Rice, white, long-grain, regular, enriched, cooked", 1.5, "1 cup"),
    (1, "19:30", "Fish, salmon, Atlantic, farmed, cooked, dry heat", 170, "g"),
    (1, "19:30", "Sweet potato, cooked, baked in skin, flesh, without salt", 200, "g"),
    (1, "21:00", "Peanut butter, smooth style, without salt", 1, "2 tbsp"),
    (2, "07:30", "Cereals, oats, regular and quick, not fortified, dry", 60, "g"),
    (2, "07:30", "Milk, reduced fat, fluid, 2% milkfat, with added vitamin A and vitamin D", 1, "1 cup"),
    (2, "12:15", "888849009305", 1, "serving"),
    (2, "19:45", "Fish, salmon, Atlantic, farmed, cooked, dry heat", 150, "g"),
    (2, "19:45", "Avocados, raw, all commercial varieties", 75, "g"),
    (2, "19:45", "Rice, white, long-grain, regular, enriched, cooked", 1, "1 cup"),
    (4, "09:00", "Egg, whole, cooked, scrambled", 3, "1 large"),
    (4, "13:30", "Chicken, broilers or fryers, breast, meat only, cooked, roasted", 180, "g"),
    (4, "13:30", "Sweet potato, cooked, baked in skin, flesh, without salt", 250, "g"),
    (4, "20:00", "076840400058", 1, "serving"),
]


def _demo_food(db: Session, key: str) -> Food | None:
    q = select(Food).options(selectinload(Food.portions))
    q = q.where(Food.barcode == key.zfill(14)) if key.isdigit() else q.where(Food.name == key, Food.source == "usda_sr_legacy")
    return db.scalar(q.limit(1))


def ensure_demo_nutrition(db: Session, today: date | None = None) -> int:
    """Give the demo user a realistic week of food entries (once). Returns entries created."""
    user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
    if user is None or db.scalar(select(func.count()).select_from(FoodEntry).where(FoodEntry.user_id == user.id)):
        return 0
    today = today or date.today()
    # The demo profile existed before this history, so its first target is dated before it.
    first = db.scalar(select(NutritionTarget).where(NutritionTarget.user_id == user.id).order_by(NutritionTarget.id).limit(1))
    if first is not None:
        first.created_at = datetime.now(UTC) - timedelta(days=30)
    created = 0
    for days_ago, hhmm, key, quantity, unit in DEMO_MEALS:
        food = _demo_food(db, key)
        if food is None:
            continue
        options = nutrition.unit_options(food)
        if unit not in {o.unit for o in options}:
            match = next((o for o in options if o.label.startswith(unit + " (") or o.label.startswith(unit + ",")), None)
            if match is None:
                continue
            unit = match.unit
        snapshot = nutrition.basis_snapshot(food, options)
        values, amount, label, _ = nutrition.compute_entry(snapshot, quantity, unit)
        day = today - timedelta(days=days_ago)
        eaten_at = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time())
        db.add(FoodEntry(user_id=user.id, food_id=food.id, kind="catalog", description=food.name, brand=food.brand,
                         quantity=quantity, unit=unit, unit_label=label, amount=amount and nutrition.round1(amount),
                         nutrition_basis=snapshot, eaten_at=eaten_at, local_date=day,
                         created_at=datetime.now(UTC) - timedelta(days=days_ago), **values))
        created += 1
    db.commit()
    return created


# Demo training history. Clearly marked as demo data (Workout.is_demo) and shown with a "Demo" badge.
# Weights are illustrative starting loads for the demo profile, by movement pattern.
DEMO_WEIGHTS_KG = {"squat": 80, "hinge": 90, "lunge": 16, "push_h": 70, "push_v": 22, "pull_v": 55, "pull_h": 60,
                   "lateral": 8, "biceps": 12, "triceps": 25, "rear_delt": 15, "knee_flex": 35, "knee_ext": 40,
                   "calf": 60, "chest_fly": 12}
DEMO_SESSIONS = [(4, "upper", 88), (2, "lower", 71)]  # (days ago, day type, actual minutes)


def ensure_demo_training(db: Session) -> int:
    """Two completed demo sessions (generated by the real generator, flagged is_demo). Returns sessions created."""
    from app.routers.training import _context, _history  # noqa: PLC0415 (avoid an import cycle at module load)
    from app.services.workout_generator import generate  # noqa: PLC0415

    user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
    if user is None or db.scalar(select(func.count()).select_from(Workout).where(Workout.user_id == user.id)):
        return 0
    created = 0
    for days_ago, day_type, actual_min in DEMO_SESSIONS:
        ctx, profile = _context(db, user)
        plan = generate(ctx=ctx, preferred_split=profile.preferred_split, days_per_week=profile.days_per_week,
                        history=_history(db, user.id), day_type=day_type)
        start = datetime.now(UTC).replace(hour=17, minute=30, second=0, microsecond=0) - timedelta(days=days_ago)
        w = Workout(user_id=user.id, status="completed", name=plan.name, split=plan.split, day_type=plan.day_type,
                    goal=ctx.goal, objective=plan.objective, explanation=plan.explanation, generator=plan.generator,
                    budget_minutes=ctx.budget_minutes, planned_seconds=plan.est_seconds, is_demo=True,
                    constraints={"equipment": sorted(ctx.equipment), "note": "demo data"},
                    created_at=start - timedelta(minutes=5), started_at=start,
                    finished_at=start + timedelta(minutes=actual_min), actual_seconds=actual_min * 60)
        for pos, it in enumerate(plan.items):
            we = WorkoutExercise(user_id=user.id, position=pos, exercise_id=it.exercise.id, name=it.exercise.name,
                                 pattern=it.exercise.pattern, slot_patterns=list(it.slot_patterns), role=it.role,
                                 measure=it.exercise.measure, target_sets=it.sets, rep_low=it.rep_low, rep_high=it.rep_high,
                                 target_seconds=it.target_seconds, rest_seconds=it.rest_s, est_seconds=it.est_seconds,
                                 instructions=list(it.exercise.instructions), notes=it.notes, completed=True)
            for n in range(1, it.sets + 1):
                reps = None if it.target_seconds else (it.rep_high if n == 1 else (it.rep_low or 8) + 1)
                weight = DEMO_WEIGHTS_KG.get(it.exercise.pattern) if it.exercise.equipment != ("body only",) else None
                we.sets.append(WorkoutSet(user_id=user.id, set_index=n, reps=reps, weight_kg=weight,
                                          duration_seconds=it.target_seconds, logged_at=start + timedelta(minutes=8 * pos + 2 * n)))
            w.exercises.append(we)
        db.add(w)
        db.commit()
        created += 1
    return created
