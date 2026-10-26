"""Food catalog (search, barcode, recent) and the user's food log.

All nutrition numbers come from deterministic code (services/nutrition.py); no AI calls.
Every entry query is filtered by the logged-in user's id; other users' ids return 404.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Food, FoodEntry, NutritionTarget, User
from app.security import current_user
from app.services import catalog, food_search, nutrition
from app.services.barcode import BarcodeError, normalize
from app.services.targets import protein_status
from app.services.plausibility import Assessment, assess_catalog_entry, assess_manual_entry

router = APIRouter(prefix="/api", tags=["nutrition"])
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------------------------------------------------------------- schemas

def _local_time(v: datetime) -> datetime:
    if v.tzinfo is not None:
        raise ValueError("send the local time without a time zone, e.g. 2026-10-25T08:30")
    if not 2000 <= v.year <= 2100:
        raise ValueError("date must be between 2000 and 2100")
    return v.replace(second=0, microsecond=0)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntryIn(Strict):
    food_id: int
    quantity: float
    unit: str = Field(max_length=40)
    eaten_at: datetime
    confirm: bool = False

    @field_validator("eaten_at")
    @classmethod
    def _t(cls, v: datetime) -> datetime:
        return _local_time(v)


class ManualEntryIn(Strict):
    description: str = Field(min_length=1, max_length=200)
    kcal: float
    protein_g: float = 0
    carb_g: float = 0
    fat_g: float = 0
    quantity: float = 1
    eaten_at: datetime
    confirm: bool = False

    @field_validator("eaten_at")
    @classmethod
    def _t(cls, v: datetime) -> datetime:
        return _local_time(v)

    @field_validator("description")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = "".join(ch for ch in v if ch.isprintable()).strip()
        if not v:
            raise ValueError("description is required")
        return v


class EntryPatch(Strict):
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    eaten_at: datetime | None = None
    confirm: bool = False

    @field_validator("eaten_at")
    @classmethod
    def _t(cls, v: datetime | None) -> datetime | None:
        return None if v is None else _local_time(v)


# ---------------------------------------------------------------- serializers

def display_barcode(gtin14: str | None) -> str | None:
    """Show the stored GTIN-14 the way it is printed: UPC-A (12 digits) when possible, else EAN-13/GTIN-14."""
    if gtin14 is None:
        return None
    core = gtin14.lstrip("0")
    return core.zfill(12) if len(core) <= 12 else core.zfill(13) if len(core) == 13 else core

def _per100(food: Food) -> dict:
    return {"kcal": food.kcal_100, "protein_g": food.protein_100, "carb_g": food.carb_100, "fat_g": food.fat_100}


def _food_summary(food: Food) -> dict:
    options = nutrition.unit_options(food)
    default = options[0]
    return {
        "id": food.id, "name": food.name, "brand": food.brand, "category": food.category,
        "source": food.source, "source_label": catalog.SOURCE_LABELS.get(food.source, food.source),
        "barcode": display_barcode(food.barcode), "basis": food.basis, "per_100": _per100(food),
        "default_unit": {"unit": default.unit, "label": default.label, "size": default.size,
                         "nutrition": nutrition.nutrition_for(nutrition.per_100(food), default.size)},
    }


def _food_detail(food: Food) -> dict:
    return {
        **_food_summary(food),
        "source_ref": food.source_ref, "published": food.published,
        "serving_size": food.serving_size, "serving_label": food.serving_label,
        "units": [{"unit": o.unit, "label": o.label, "size": o.size, "kind": o.kind} for o in nutrition.unit_options(food)],
    }


def _entry_out(e: FoodEntry) -> dict:
    snap = e.nutrition_basis
    return {
        "id": e.id, "food_id": e.food_id, "kind": e.kind, "description": e.description, "brand": e.brand,
        "quantity": e.quantity, "unit": e.unit, "unit_label": e.unit_label, "amount": e.amount,
        "basis": snap.get("basis"), "kcal": e.kcal, "protein_g": e.protein_g, "carb_g": e.carb_g, "fat_g": e.fat_g,
        "eaten_at": e.eaten_at.strftime("%Y-%m-%dT%H:%M"), "local_date": e.local_date.isoformat(),
        "units": [{"unit": u, **info} for u, info in snap["units"].items()],
        "source_label": catalog.SOURCE_LABELS.get(snap.get("source", ""), "Entered by you"),
        "created_at": e.created_at, "updated_at": e.updated_at,
    }


# ---------------------------------------------------------------- helpers

def _food_or_404(db: Session, food_id: int) -> Food:
    food = db.scalar(select(Food).where(Food.id == food_id).options(selectinload(Food.portions)))
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Food not found.")
    return food


def _own_entry(db: Session, user: User, entry_id: int) -> FoodEntry:
    e = db.scalar(select(FoodEntry).where(FoodEntry.id == entry_id, FoodEntry.user_id == user.id))
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found.")
    return e


def _day_kcal(db: Session, user_id: int, day: date, exclude_id: int | None = None) -> float:
    q = select(func.coalesce(func.sum(FoodEntry.kcal), 0.0)).where(
        FoodEntry.user_id == user_id, FoodEntry.local_date == day)
    if exclude_id is not None:
        q = q.where(FoodEntry.id != exclude_id)
    return float(db.scalar(q) or 0.0)


def _enforce(a: Assessment, confirm: bool, preview: dict) -> None:
    if a.errors:
        raise HTTPException(UNPROCESSABLE, a.errors)
    if a.warnings and not confirm:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "code": "confirmation_required", "warnings": a.warnings,
            "suggestions": a.suggestions, "preview": preview,
        })


def _compute(snapshot: dict, quantity: float, unit: str):
    try:
        return nutrition.compute_entry(snapshot, quantity, unit)
    except KeyError:
        raise HTTPException(UNPROCESSABLE, [f"'{unit}' is not a valid unit for this food."]) from None


def local_day_end_utc(day: date, tz_offset_minutes: int | None) -> datetime:
    """Midnight after `day` in the user's local time, as naive UTC (how SQLite stores timestamps).
    tz_offset_minutes is the browser's Date.getTimezoneOffset() (minutes behind UTC); without it the
    server's local time zone is assumed (correct for the local, single-user setup)."""
    end_local = datetime.combine(day + timedelta(days=1), datetime.min.time())
    if tz_offset_minutes is not None:
        return end_local + timedelta(minutes=tz_offset_minutes)
    return end_local.astimezone(UTC).replace(tzinfo=None)


def target_for_day(db: Session, user_id: int, day: date, tz_offset_minutes: int | None = None) -> NutritionTarget | None:
    """The target that was in effect on `day`: the newest one created before that local day ended.
    Days before the first target have no target (Venn does not back-fill one)."""
    end = local_day_end_utc(day, tz_offset_minutes)
    return db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user_id, NutritionTarget.created_at < end)
        .order_by(NutritionTarget.created_at.desc(), NutritionTarget.id.desc()).limit(1))


# ---------------------------------------------------------------- foods

@router.get("/foods/search")
def search_foods(q: str = Query(min_length=1, max_length=100), limit: int = Query(20, ge=1, le=50),
                 user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    recent_ids = frozenset(db.scalars(
        select(FoodEntry.food_id).where(FoodEntry.user_id == user.id, FoodEntry.food_id.is_not(None))
        .order_by(FoodEntry.created_at.desc()).limit(50)))
    ids = food_search.search(catalog.search_index(db), q, limit, recent_ids)
    foods = {f.id: f for f in db.scalars(select(Food).where(Food.id.in_(ids)).options(selectinload(Food.portions)))}
    return {"query": q, "results": [_food_summary(foods[i]) for i in ids if i in foods]}


@router.get("/foods/recent")
def recent_foods(limit: int = Query(12, ge=1, le=30), user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Foods this user logged, most recently logged first, with the last quantity used."""
    last = (select(FoodEntry.food_id, func.max(FoodEntry.id).label("last_id"), func.count().label("times"))
            .where(FoodEntry.user_id == user.id, FoodEntry.food_id.is_not(None))
            .group_by(FoodEntry.food_id).subquery())
    rows = db.execute(
        select(FoodEntry, last.c.times).join(last, FoodEntry.id == last.c.last_id)
        .order_by(FoodEntry.created_at.desc(), FoodEntry.id.desc()).limit(limit)).all()
    foods = {f.id: f for f in db.scalars(
        select(Food).where(Food.id.in_([e.food_id for e, _ in rows])).options(selectinload(Food.portions)))}
    out = []
    for e, times in rows:
        food = foods.get(e.food_id)
        if food is None:
            continue
        valid_units = {o.unit for o in nutrition.unit_options(food)}
        out.append({**_food_summary(food), "times_logged": times,
                    "last": {"quantity": e.quantity, "unit": e.unit if e.unit in valid_units else food.basis,
                             "unit_label": e.unit_label, "kcal": e.kcal, "eaten_at": e.eaten_at.strftime("%Y-%m-%dT%H:%M")}})
    return {"results": out}


@router.get("/foods/barcode/{code}")
def barcode_lookup(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    try:
        gtin = normalize(code)
    except BarcodeError as error:
        raise HTTPException(UNPROCESSABLE, [str(error)]) from error
    food = db.scalar(select(Food).where(Food.barcode == gtin).options(selectinload(Food.portions)))
    if food is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, {
            "code": "barcode_not_found",
            "message": "This barcode isn't in Venn's offline product sample. Search for the food or enter it manually.",
            "barcode": code.strip()})
    return _food_detail(food)


@router.get("/foods/barcodes")
def sample_barcodes(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """The packaged products available for barcode lookup (helps testers find a valid code)."""
    rows = db.scalars(select(Food).where(Food.barcode.is_not(None)).order_by(Food.brand, Food.name))
    return {"products": [{"barcode": display_barcode(f.barcode), "name": f.name, "brand": f.brand} for f in rows]}


@router.get("/foods/{food_id}")
def food_detail(food_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _food_detail(_food_or_404(db, food_id))


# ---------------------------------------------------------------- entries

@router.post("/nutrition/entries", status_code=status.HTTP_201_CREATED)
def add_entry(body: EntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    food = _food_or_404(db, body.food_id)
    snapshot = nutrition.basis_snapshot(food, nutrition.unit_options(food))
    values, amount, label, kind = _compute(snapshot, body.quantity, body.unit)
    day = body.eaten_at.date()
    a = assess_catalog_entry(body.quantity, body.unit, kind, food.basis, amount, values["kcal"], _day_kcal(db, user.id, day))
    _enforce(a, body.confirm, {**values, "amount": amount})
    e = FoodEntry(user_id=user.id, food_id=food.id, kind="catalog", description=food.name, brand=food.brand,
                  quantity=body.quantity, unit=body.unit, unit_label=label, amount=amount and nutrition.round1(amount),
                  nutrition_basis=snapshot, eaten_at=body.eaten_at, local_date=day, **values)
    db.add(e)
    db.commit()
    return _entry_out(e)


@router.post("/nutrition/entries/manual", status_code=status.HTTP_201_CREATED)
def add_manual_entry(body: ManualEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    per_serving = {"kcal": body.kcal, "protein_g": body.protein_g, "carb_g": body.carb_g, "fat_g": body.fat_g}
    day = body.eaten_at.date()
    a = assess_manual_entry(body.quantity, per_serving, _day_kcal(db, user.id, day))
    if a.errors:
        raise HTTPException(UNPROCESSABLE, a.errors)
    snapshot = nutrition.manual_snapshot(per_serving)
    values, _, label, _ = _compute(snapshot, body.quantity, "serving")
    _enforce(a, body.confirm, values)
    e = FoodEntry(user_id=user.id, food_id=None, kind="manual", description=body.description, brand="",
                  quantity=body.quantity, unit="serving", unit_label=label, amount=None,
                  nutrition_basis=snapshot, eaten_at=body.eaten_at, local_date=day, **values)
    db.add(e)
    db.commit()
    return _entry_out(e)


@router.patch("/nutrition/entries/{entry_id}")
def edit_entry(entry_id: int, body: EntryPatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    e = _own_entry(db, user, entry_id)
    quantity = body.quantity if body.quantity is not None else e.quantity
    unit = body.unit if body.unit is not None else e.unit
    eaten_at = body.eaten_at or e.eaten_at
    values, amount, label, kind = _compute(e.nutrition_basis, quantity, unit)
    day = eaten_at.date()
    other = _day_kcal(db, user.id, day, exclude_id=e.id)
    if e.kind == "manual":
        a = assess_manual_entry(quantity, e.nutrition_basis["values"], other)
        a.warnings = [w for w in a.warnings if "macros add up" not in w]  # already accepted when created
    else:
        a = assess_catalog_entry(quantity, unit, kind, e.nutrition_basis.get("basis"), amount, values["kcal"], other)
    if body.quantity is not None or body.unit is not None:
        _enforce(a, body.confirm, {**values, "amount": amount})
    elif a.errors:
        raise HTTPException(UNPROCESSABLE, a.errors)
    e.quantity, e.unit, e.unit_label = quantity, unit, label
    e.amount = amount and nutrition.round1(amount)
    e.eaten_at, e.local_date = eaten_at, day
    for k, v in values.items():
        setattr(e, k, v)
    db.commit()
    return _entry_out(e)


@router.delete("/nutrition/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    db.delete(_own_entry(db, user, entry_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/nutrition/entries/{entry_id}")
def get_entry(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _entry_out(_own_entry(db, user, entry_id))


@router.get("/nutrition/day")
def day_summary(day: date = Query(alias="date"), tz_offset: int | None = Query(default=None, ge=-900, le=900),
                user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    entries = list(db.scalars(
        select(FoodEntry).where(FoodEntry.user_id == user.id, FoodEntry.local_date == day)
        .order_by(FoodEntry.eaten_at, FoodEntry.id)))
    total = nutrition.totals(entries)
    target = target_for_day(db, user.id, day, tz_offset)
    tvals = {"kcal": target.kcal, "protein_g": target.protein_g, "carb_g": target.carb_g, "fat_g": target.fat_g} if target else None
    return {
        "date": day.isoformat(),
        "entries": [_entry_out(e) for e in entries],
        "totals": total,
        "target": ({**tvals, "id": target.id, "method": target.method} if target else None),
        "progress": {k: nutrition.progress(total[k], tvals[k] if tvals else None) for k in nutrition.NUTRIENTS},
        "protein_range": protein_status(total["protein_g"], (target.breakdown or {}).get("protein_unrounded", target.protein_g)) if target else None,
    }


@router.get("/nutrition/week")
def week_summary(end: date = Query(), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    start = end - timedelta(days=6)
    rows = db.execute(
        select(FoodEntry.local_date, func.count(), func.sum(FoodEntry.kcal))
        .where(FoodEntry.user_id == user.id, FoodEntry.local_date >= start, FoodEntry.local_date <= end)
        .group_by(FoodEntry.local_date)).all()
    by_day = {d: (n, k) for d, n, k in rows}
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        n, k = by_day.get(d, (0, 0.0))
        days.append({"date": d.isoformat(), "entries": n, "kcal": nutrition.round1(k or 0.0)})
    return {"start": start.isoformat(), "end": end.isoformat(), "days": days,
            "days_logged": sum(1 for d in days if d["entries"] > 0)}
