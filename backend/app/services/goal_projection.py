"""Optional target-weight projection. Informational only: it does not change calorie targets.

Calorie targets still come from services/targets.py (the existing, tested formula with its
safety limits). This module only answers "at the pace you chose, roughly when would you reach
your target weight?" and "is your target date possible within Venn's maximum safe pace?".
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from app.services.targets import MAX_RATE_PCT

# User-facing pace choices -> % of body weight per week (stored as goal_rate_pct).
PACE_RATES = {
    "lose": {"gradual": 0.25, "moderate": 0.5, "faster": 0.75},
    "gain": {"gradual": 0.1, "moderate": 0.25, "faster": 0.5},
}


def projection(goal: str | None, weight_kg: float | None, rate_pct: float, target_kg: float | None,
               target_date: date | None, today: date | None = None) -> dict | None:
    if goal not in ("lose", "gain") or not weight_kg or not target_kg:
        return None
    today = today or date.today()
    diff = abs(target_kg - weight_kg)
    weekly_kg = rate_pct / 100 * weight_kg
    out: dict = {"target_weight_kg": target_kg, "change_kg": round(diff, 1)}
    if weekly_kg > 0:
        weeks = math.ceil(diff / weekly_kg)
        out.update(weeks_at_pace=weeks, estimated_date=(today + timedelta(weeks=weeks)).isoformat(),
                   weekly_change_kg=round(weekly_kg, 2))
    if target_date:
        weeks_available = max((target_date - today).days / 7, 0)
        if weeks_available <= 0:
            out["date_check"] = "The target date has passed. Choose a future date or remove it."
        else:
            needed_pct = diff / weeks_available / weight_kg * 100
            out["required_rate_pct"] = round(needed_pct, 2)
            limit = MAX_RATE_PCT[goal]
            if needed_pct > limit:
                min_weeks = math.ceil(diff / (limit / 100 * weight_kg))
                out["date_check"] = (f"Reaching {target_kg:g} kg by {target_date.isoformat()} would need about "
                                     f"{needed_pct:.2f}% of body weight per week, above Venn's maximum of {limit}%. "
                                     f"At the maximum pace it would take about {min_weeks} weeks "
                                     f"({(today + timedelta(weeks=min_weeks)).isoformat()}).")
            else:
                out["date_check"] = (f"Your target date needs about {needed_pct:.2f}% of body weight per week, "
                                     f"within Venn's limit of {limit}%.")
    return out
