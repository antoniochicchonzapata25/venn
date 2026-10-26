"""Deterministic nutrition math: units, per-entry nutrition, daily totals and progress.

No AI is involved anywhere in this module.

Catalog values are per 100 g (or per 100 ml for liquids). An entry's nutrition is
    value = value_per_100 x amount / 100,   amount = quantity x unit size (g or ml).
Values are stored rounded to 0.1 (half up); daily totals are sums of stored values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

GRAMS_PER = {"g": 1.0, "kg": 1000.0, "oz": 28.349523125, "lb": 453.59237}
ML_PER = {"ml": 1.0, "l": 1000.0, "fl_oz": 29.5735295625}
UNIT_LABELS = {"g": "g", "kg": "kg", "oz": "oz", "lb": "lb", "ml": "ml", "l": "L", "fl_oz": "fl oz"}
NUTRIENTS = ("kcal", "protein_g", "carb_g", "fat_g")


def round1(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class UnitOption:
    unit: str  # "g", "oz", "portion:12", "serving", ...
    label: str  # "1 cup, chopped (140 g)"
    size: float  # grams or ml per 1 of this unit
    kind: str  # "mass" | "volume" | "count"


_LABEL_UNITS = {"GRM": "g", "ONZ": "oz", "MLT": "ml", "OZA": "fl oz"}


def tidy_label(text: str) -> str:
    """Branded labels use GS1 unit codes ("125 GRM"); show them as normal units ("125 g")."""
    return re.sub(r"\b(GRM|ONZ|MLT|OZA)\b", lambda m: _LABEL_UNITS[m.group(1)], text).strip()


def unit_options(food) -> list[UnitOption]:  # noqa: ANN001  (models.Food)
    """All units a food can be logged in, most useful first."""
    basis = food.basis
    options: list[UnitOption] = []
    if food.serving_size:
        text = tidy_label(food.serving_label) or "1 serving"
        options.append(UnitOption("serving", f"serving: {text} ({food.serving_size:g} {basis})", food.serving_size, "count"))
    for p in food.portions:
        options.append(UnitOption(f"portion:{p.id}", f"{p.label} ({p.amount:g} {basis})", p.amount, "count"))
    table, kind = (GRAMS_PER, "mass") if basis == "g" else (ML_PER, "volume")
    options.extend(UnitOption(u, UNIT_LABELS[u], size, kind) for u, size in table.items())
    return options


def per_100(food) -> dict[str, float]:  # noqa: ANN001
    return {"kcal": food.kcal_100, "protein_g": food.protein_100, "carb_g": food.carb_100, "fat_g": food.fat_100}


def nutrition_for(per100: dict[str, float], amount: float) -> dict[str, float]:
    return {k: round1(per100[k] * amount / 100) for k in NUTRIENTS}


def scale_per_unit(per_unit: dict[str, float], quantity: float) -> dict[str, float]:
    """Manual entries store nutrition for one serving."""
    return {k: round1(per_unit[k] * quantity) for k in NUTRIENTS}


def basis_snapshot(food, options: list[UnitOption]) -> dict:  # noqa: ANN001
    """Everything needed to recompute an entry later without the catalog."""
    return {
        "kind": "per_100", "basis": food.basis, "values": per_100(food),
        "units": {o.unit: {"label": o.label, "size": o.size, "kind": o.kind} for o in options},
        "source": food.source, "source_ref": food.source_ref,
    }


def manual_snapshot(values: dict[str, float]) -> dict:
    return {"kind": "per_serving", "values": values,
            "units": {"serving": {"label": "serving", "size": 1.0, "kind": "count"}}}


def compute_entry(snapshot: dict, quantity: float, unit: str) -> tuple[dict[str, float], float | None, str, str]:
    """-> (nutrition, amount in g/ml or None, unit label, unit kind). Raises KeyError for unknown units."""
    unit_info = snapshot["units"][unit]
    if snapshot["kind"] == "per_serving":
        return scale_per_unit(snapshot["values"], quantity), None, unit_info["label"], unit_info["kind"]
    amount = quantity * unit_info["size"]
    return nutrition_for(snapshot["values"], amount), amount, unit_info["label"], unit_info["kind"]


def totals(entries) -> dict[str, float]:  # noqa: ANN001
    out = {k: 0.0 for k in NUTRIENTS}
    for e in entries:
        for k in NUTRIENTS:
            out[k] += getattr(e, k)
    return {k: round1(v) for k, v in out.items()}


def progress(consumed: float, target: float | None) -> dict:
    """Progress toward one daily target.

    state: "no_target" | "empty" | "partial" | "met" | "over". "met" means the consumed
    amount equals the target when both are rounded to whole units (what the user sees).
    """
    consumed = round1(consumed)
    if target is None:
        return {"consumed": consumed, "target": None, "remaining": None, "over": None, "percent": None, "state": "no_target"}
    if round(consumed) == round(target):
        state = "met"
    elif consumed == 0:
        state = "empty"
    elif consumed < target:
        state = "partial"
    else:
        state = "over"
    return {
        "consumed": consumed,
        "target": target,
        "remaining": round1(max(target - consumed, 0.0)),
        "over": round1(max(consumed - target, 0.0)),
        "percent": round1(consumed / target * 100) if target else None,
        "state": state,
    }
