"""Daily calorie and macronutrient targets: transparent, deterministic formulas.

These are general estimates for healthy adults, not medical or dietetic advice.

Method
1. Resting energy (BMR), Mifflin-St Jeor (1990):
     10 x weight_kg + 6.25 x height_cm - 5 x age + s,   s = +5 (male), -161 (female),
     -78 (unspecified: the midpoint of the two).
2. Maintenance (TDEE) = BMR x activity multiplier (1.2 / 1.375 / 1.55 / 1.725 / 1.9).
3. Goal adjustment: weekly change = goal_rate_pct % of body weight; 1 kg of body
   weight ~ 7,700 kcal, so the daily change = rate/100 x weight x 7,700 / 7
   (negative to lose, positive to gain).
4. Calories rounded to the nearest 10 kcal, then raised to the safety minimum if
   needed: the higher of a sex-based minimum (1,200 female / 1,500 male / 1,200
   unspecified) and the estimated BMR. When raised, the minimum is rounded *up*.
5. Protein = g/kg x reference weight (1.6 / 2.0 / 2.2), capped at 35% of calories.
   Reference weight = current weight, except when the user is deliberately losing scale weight
   and has set a target weight: then the target weight (see docs/protein_review.md).
6. Fat = 30% / 40% / 20% of calories (balanced / lower-carb / lower-fat), at least 0.5 g/kg,
   at most 40% of calories.
7. Carbohydrate = the remaining calories / 4 (4 kcal/g protein and carb, 9 kcal/g fat).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal

SEX_OFFSET = {"male": 5.0, "female": -161.0, "unspecified": -78.0}
SEX_MIN_KCAL = {"male": 1500, "female": 1200, "unspecified": 1200}
ACTIVITY_MULTIPLIER = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very": 1.725, "extra": 1.9}
PROTEIN_G_PER_KG = {"standard": 1.6, "high": 2.0, "very_high": 2.2}
FAT_SHARE = {"balanced": 0.30, "lower_carb": 0.40, "lower_fat": 0.20}
MAX_RATE_PCT = {"lose": 1.0, "maintain": 0.0, "gain": 0.5}
KCAL_PER_KG = 7700
PROTEIN_MAX_SHARE = 0.35
FAT_MIN_G_PER_KG = 0.5
FAT_MAX_SHARE = 0.40
MAX_KCAL = 6000
MIN_AGE, MAX_AGE = 18, 100
HEIGHT_RANGE_CM = (120.0, 230.0)
WEIGHT_RANGE_KG = (35.0, 300.0)
MANUAL_ENERGY_TOLERANCE = 0.10  # manual macros must add up to within 10% of the calories

DISCLAIMER = (
    "These targets are estimates from general population formulas. They are not medical advice and "
    "may not suit everyone. Talk to a qualified professional if you are pregnant, under 18, managing a "
    "medical condition, or have a history of disordered eating."
)


class TargetInputError(ValueError):
    """Inputs are outside the ranges the formulas are valid for."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def round_half_up(value: float, step: int = 1) -> int:
    """Schoolbook rounding (Python's round() uses banker's rounding)."""
    q = Decimal(str(value)) / Decimal(step)
    return int(q.quantize(Decimal(1), rounding=ROUND_HALF_UP)) * step


@dataclass(frozen=True)
class TargetInputs:
    sex: str
    age: int
    height_cm: float
    weight_kg: float
    activity_level: str
    goal: str
    goal_rate_pct: float = 0.0
    protein_level: str = "standard"
    diet_style: str = "balanced"
    target_weight_kg: float | None = None


@dataclass
class TargetResult:
    kcal: int
    protein_g: int
    carb_g: int
    fat_g: int
    bmr: float
    activity_multiplier: float
    tdee: float
    daily_energy_change: float
    unrounded_kcal: float
    minimum_kcal: float
    minimum_applied: bool
    protein_capped: bool
    protein_reference: str
    protein_reference_kg: float
    protein_g_per_kg: float
    protein_unrounded: float
    fat_floor_applied: bool
    estimated_weekly_change_kg: float
    inputs: dict
    warnings: list[str] = field(default_factory=list)

    def breakdown(self) -> dict:
        data = asdict(self)
        for key in ("kcal", "protein_g", "carb_g", "fat_g"):
            data.pop(key)
        return data


def validate_inputs(i: TargetInputs) -> None:
    errors: list[str] = []
    if i.sex not in SEX_OFFSET:
        errors.append("sex must be male, female or unspecified")
    if not MIN_AGE <= i.age <= MAX_AGE:
        errors.append(f"age must be between {MIN_AGE} and {MAX_AGE}; Venn's targets are for adults only")
    if not HEIGHT_RANGE_CM[0] <= i.height_cm <= HEIGHT_RANGE_CM[1]:
        errors.append(f"height must be between {HEIGHT_RANGE_CM[0]:.0f} and {HEIGHT_RANGE_CM[1]:.0f} cm")
    if not WEIGHT_RANGE_KG[0] <= i.weight_kg <= WEIGHT_RANGE_KG[1]:
        errors.append(f"weight must be between {WEIGHT_RANGE_KG[0]:.0f} and {WEIGHT_RANGE_KG[1]:.0f} kg")
    if i.activity_level not in ACTIVITY_MULTIPLIER:
        errors.append("unknown activity level")
    if i.goal not in MAX_RATE_PCT:
        errors.append("goal must be lose, maintain or gain")
    elif i.goal_rate_pct < 0 or i.goal_rate_pct > MAX_RATE_PCT[i.goal]:
        if i.goal == "maintain":
            errors.append("goal rate must be 0 when maintaining")
        else:
            errors.append(f"goal rate for '{i.goal}' must be between 0 and {MAX_RATE_PCT[i.goal]}% of body weight per week")
    if i.protein_level not in PROTEIN_G_PER_KG:
        errors.append("unknown protein level")
    if i.diet_style not in FAT_SHARE:
        errors.append("unknown diet style")
    if errors:
        raise TargetInputError(errors)


def calculate_targets(i: TargetInputs) -> TargetResult:
    validate_inputs(i)
    warnings: list[str] = []

    bmr = 10 * i.weight_kg + 6.25 * i.height_cm - 5 * i.age + SEX_OFFSET[i.sex]
    multiplier = ACTIVITY_MULTIPLIER[i.activity_level]
    tdee = bmr * multiplier
    sign = {"lose": -1, "maintain": 0, "gain": 1}[i.goal]
    daily_change = sign * (i.goal_rate_pct / 100) * i.weight_kg * KCAL_PER_KG / 7
    unrounded = tdee + daily_change

    minimum = max(SEX_MIN_KCAL[i.sex], bmr)
    kcal = round_half_up(unrounded, 10)
    minimum_applied = kcal < minimum
    if minimum_applied:
        kcal = int(math.ceil(minimum / 10) * 10)
        warnings.append(
            f"Calories were raised to the safety minimum of {kcal} kcal. Expect slower progress than the rate you chose."
        )
    if kcal > MAX_KCAL:
        raise TargetInputError([f"calculated calories exceed the {MAX_KCAL} kcal limit; please check your inputs"])

    ref_kg, ref_label = protein_reference(i)
    protein = ref_kg * PROTEIN_G_PER_KG[i.protein_level]
    protein_capped = protein * 4 > PROTEIN_MAX_SHARE * kcal
    if protein_capped:
        protein = PROTEIN_MAX_SHARE * kcal / 4
        warnings.append("Protein was capped at 35% of calories.")
    protein_g = round_half_up(protein)

    fat = FAT_SHARE[i.diet_style] * kcal / 9
    fat_floor = FAT_MIN_G_PER_KG * i.weight_kg
    fat_floor_applied = fat < fat_floor
    if fat_floor_applied:
        fat = min(fat_floor, FAT_MAX_SHARE * kcal / 9)
    fat_g = round_half_up(fat)

    carb_g = round_half_up((kcal - 4 * protein_g - 9 * fat_g) / 4)
    if carb_g < 0:  # cannot happen with the caps above; kept as a hard guard
        raise TargetInputError(["could not fit protein and fat within the calorie target"])

    weekly_change = (kcal - tdee) * 7 / KCAL_PER_KG
    if i.goal == "lose" and weekly_change >= 0:
        warnings.append("At the safety minimum these calories are not below your estimated maintenance.")

    return TargetResult(
        kcal=kcal, protein_g=protein_g, carb_g=carb_g, fat_g=fat_g,
        bmr=round(bmr, 2), activity_multiplier=multiplier, tdee=round(tdee, 2),
        daily_energy_change=round(daily_change, 2), unrounded_kcal=round(unrounded, 2),
        minimum_kcal=round(minimum, 2), minimum_applied=minimum_applied,
        protein_capped=protein_capped, fat_floor_applied=fat_floor_applied,
        protein_reference=ref_label, protein_reference_kg=round(ref_kg, 2),
        protein_g_per_kg=PROTEIN_G_PER_KG[i.protein_level], protein_unrounded=round(protein, 2),
        estimated_weekly_change_kg=round(weekly_change, 3),
        inputs=asdict(i), warnings=warnings,
    )


def protein_reference(i: TargetInputs) -> tuple[float, str]:
    """Which body weight the g/kg protein multiplier is applied to.

    Current weight by default. When the user is deliberately losing scale weight AND has set a
    target weight, the (lower) target weight is used, so protein is not scaled to weight the user
    plans to lose. Body-fat % and BMI are not used (self-reported, not reliable enough here).
    """
    if i.goal == "lose" and i.target_weight_kg and WEIGHT_RANGE_KG[0] <= i.target_weight_kg < i.weight_kg:
        return i.target_weight_kg, "target weight"
    return i.weight_kg, "current weight"


PROTEIN_TOLERANCE = 0.05  # usability tolerance around the nominal target (not a physiological threshold)


def protein_range(nominal_unrounded: float) -> tuple[int, int]:
    """Acceptable daily range: nominal +/- 5%, computed from the unrounded target, rounded half-up."""
    return (round_half_up(nominal_unrounded * (1 - PROTEIN_TOLERANCE)),
            round_half_up(nominal_unrounded * (1 + PROTEIN_TOLERANCE)))


def protein_status(consumed: float, nominal_unrounded: float | None) -> dict | None:
    """Compare whole grams eaten with the whole-gram range: below / within / above."""
    if nominal_unrounded is None:
        return None
    low, high = protein_range(nominal_unrounded)
    eaten = round_half_up(consumed)
    if eaten < low:
        state, gap = "below", low - eaten
    elif eaten > high:
        state, gap = "above", eaten - high
    else:
        state, gap = "within", 0
    return {"low": low, "high": high, "nominal": round_half_up(nominal_unrounded), "eaten": eaten,
            "state": state, "to_low": gap if state == "below" else 0, "above_high": gap if state == "above" else 0}


def validate_manual_targets(kcal: int, protein_g: int, carb_g: int, fat_g: int, sex: str | None, weight_kg: float | None) -> list[str]:
    """Rules for user-entered targets. Returns a list of errors (empty = valid)."""
    errors: list[str] = []
    minimum = SEX_MIN_KCAL.get(sex or "unspecified", SEX_MIN_KCAL["unspecified"])
    if kcal < minimum:
        errors.append(f"calories must be at least {minimum} kcal (Venn's safety minimum)")
    if kcal > MAX_KCAL:
        errors.append(f"calories must be at most {MAX_KCAL} kcal")
    if min(protein_g, carb_g, fat_g) < 0:
        errors.append("macros cannot be negative")
    if fat_g < 20:
        errors.append("fat must be at least 20 g per day")
    if weight_kg and protein_g > 4 * weight_kg:
        errors.append("protein above 4 g per kg of body weight is not allowed")
    macro_kcal = 4 * protein_g + 4 * carb_g + 9 * fat_g
    if kcal > 0 and abs(macro_kcal - kcal) > MANUAL_ENERGY_TOLERANCE * kcal:
        errors.append(
            f"macros add up to {macro_kcal} kcal, which is more than 10% away from {kcal} kcal"
        )
    return errors
