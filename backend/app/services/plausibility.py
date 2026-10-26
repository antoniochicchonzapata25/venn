"""Deterministic checks that catch implausible food entries before they are saved.

Two tiers:
- errors: values that cannot be right for one entry (rejected; the user must fix them);
- warnings: unusual but possible values (saved only after the user confirms, or fixes them).

Thresholds are deliberately generous so real large meals and bulk logging still work.
The classic mistake this targets is typing a weight into a count unit
(e.g. "150 servings" instead of "150 g").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_ENTRY_AMOUNT = 25_000  # g or ml in one entry (25 kg)
MAX_ENTRY_KCAL = 30_000
MAX_QUANTITY = 100_000
WARN_ENTRY_KCAL = 3_000
WARN_ENTRY_AMOUNT = 3_000  # g or ml
WARN_COUNT_QUANTITY = 20  # servings / portions in one entry
WARN_LARGE_UNIT_QUANTITY = {"kg": 5, "l": 5, "lb": 10}
WARN_DAY_KCAL = 10_000
MACRO_MISMATCH_KCAL = 50
MACRO_MISMATCH_SHARE = 0.25


@dataclass
class Assessment:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)


def check_quantity(quantity: float) -> list[str]:
    if quantity is None or not math.isfinite(quantity):
        return ["Quantity must be a number."]
    if quantity <= 0:
        return ["Quantity must be greater than zero."]
    if quantity > MAX_QUANTITY:
        return [f"Quantity must be at most {MAX_QUANTITY:,}."]
    return []


def assess_catalog_entry(quantity: float, unit: str, unit_kind: str, basis: str | None,
                         amount: float | None, kcal: float, day_kcal_other: float) -> Assessment:
    a = Assessment(errors=check_quantity(quantity))
    if a.errors:
        return a
    base = basis or "g"
    if amount is not None and amount > MAX_ENTRY_AMOUNT:
        a.errors.append(f"{amount:,.0f} {base} in one entry is more than the {MAX_ENTRY_AMOUNT:,} {base} limit. "
                        "Check the quantity and unit, or split it into several entries.")
    if kcal > MAX_ENTRY_KCAL:
        a.errors.append(f"{kcal:,.0f} kcal in one entry is not plausible. Check the quantity and unit.")
    if a.errors:
        return a

    if unit_kind == "count" and quantity >= WARN_COUNT_QUANTITY:
        a.warnings.append(f"{quantity:g} servings is unusual. Did you mean {quantity:g} {base}?")
        a.suggestions.append({"quantity": quantity, "unit": base, "label": f"Use {quantity:g} {base} instead"})
    if unit in WARN_LARGE_UNIT_QUANTITY and quantity > WARN_LARGE_UNIT_QUANTITY[unit]:
        small = {"kg": "g", "l": "ml", "lb": "oz"}[unit]
        a.warnings.append(f"{quantity:g} {unit} is a lot for one entry. Did you mean {quantity:g} {small}?")
        a.suggestions.append({"quantity": quantity, "unit": small, "label": f"Use {quantity:g} {small} instead"})
    if amount is not None and amount > WARN_ENTRY_AMOUNT and not a.warnings:
        a.warnings.append(f"This entry is {amount:,.0f} {base}. Please confirm that is right.")
    if kcal > WARN_ENTRY_KCAL:
        a.warnings.append(f"This entry is {kcal:,.0f} kcal. Please confirm that is right.")
    if day_kcal_other + kcal > WARN_DAY_KCAL:
        a.warnings.append(f"With this entry the day totals {day_kcal_other + kcal:,.0f} kcal.")
    return a


def assess_manual_entry(quantity: float, values: dict[str, float], day_kcal_other: float) -> Assessment:
    a = Assessment(errors=check_quantity(quantity))
    if a.errors:
        return a
    if any((v is None or not math.isfinite(v) or v < 0) for v in values.values()):
        a.errors.append("Calories and macros must be zero or positive numbers.")
        return a
    kcal = values["kcal"] * quantity
    if kcal > MAX_ENTRY_KCAL:
        a.errors.append(f"{kcal:,.0f} kcal in one entry is not plausible.")
        return a
    macro_kcal = 4 * values["protein_g"] + 4 * values["carb_g"] + 9 * values["fat_g"]
    gap = abs(macro_kcal - values["kcal"])
    if gap > MACRO_MISMATCH_KCAL and gap > MACRO_MISMATCH_SHARE * max(macro_kcal, values["kcal"]):
        a.warnings.append(
            f"The macros add up to about {macro_kcal:,.0f} kcal per serving, but you entered {values['kcal']:,.0f} kcal. "
            "Please check the label.")
    if quantity >= WARN_COUNT_QUANTITY:
        a.warnings.append(f"{quantity:g} servings is unusual. Please confirm.")
    if kcal > WARN_ENTRY_KCAL:
        a.warnings.append(f"This entry is {kcal:,.0f} kcal. Please confirm that is right.")
    if day_kcal_other + kcal > WARN_DAY_KCAL:
        a.warnings.append(f"With this entry the day totals {day_kcal_other + kcal:,.0f} kcal.")
    return a
