"""Target calculator vs. independent hand calculations, plus invalid inputs and safety minimums.

Each expected value below was worked out by hand from the published formulas
(Mifflin-St Jeor; 7,700 kcal per kg; 4/4/9 kcal per gram), not by calling the code.
"""

from __future__ import annotations

import pytest

from app.services.targets import (
    TargetInputError, TargetInputs, calculate_targets, round_half_up, validate_manual_targets,
)


# --- hand-calculated cases -------------------------------------------------------------

def test_case_a_male_maintain_moderate():
    # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
    # TDEE = 1780 * 1.55 = 2759.0 -> 2760 kcal
    # protein = 1.6 * 80 = 128 g; fat = 0.30 * 2760 / 9 = 92.0 g
    # carbs = (2760 - 4*128 - 9*92) / 4 = (2760 - 512 - 828) / 4 = 355 g
    r = calculate_targets(TargetInputs("male", 30, 180, 80, "moderate", "maintain"))
    assert r.bmr == 1780
    assert r.tdee == 2759
    assert (r.kcal, r.protein_g, r.fat_g, r.carb_g) == (2760, 128, 92, 355)
    assert not r.minimum_applied and not r.protein_capped


def test_case_b_female_lose_hits_bmr_minimum_and_protein_cap():
    # BMR = 600 + 1031.25 - 125 - 161 = 1345.25 ; TDEE = 1345.25 * 1.2 = 1614.3
    # deficit = 0.005 * 60 * 7700 / 7 = 330 -> 1284.3 -> 1280, below minimum max(1200, 1345.25)
    # -> raised to 1350 (minimum rounded up to 10)
    # protein = 2.0 * 60 = 120 g = 480 kcal > 35% of 1350 (472.5) -> 472.5 / 4 = 118.125 -> 118 g
    # fat = 0.30 * 1350 / 9 = 45 g ; carbs = (1350 - 472 - 405) / 4 = 118.25 -> 118 g
    r = calculate_targets(TargetInputs("female", 25, 165, 60, "sedentary", "lose", 0.5, "high", "balanced"))
    assert r.daily_energy_change == -330
    assert r.minimum_applied and r.minimum_kcal == 1345.25
    assert r.protein_capped
    assert (r.kcal, r.protein_g, r.fat_g, r.carb_g) == (1350, 118, 45, 118)
    assert any("safety minimum" in w for w in r.warnings)


def test_case_c_male_gain_lower_carb():
    # BMR = 900 + 1093.75 - 200 + 5 = 1798.75 ; TDEE = 1798.75 * 1.725 = 3102.84375
    # surplus = 0.0025 * 90 * 7700 / 7 = 247.5 -> 3350.34 -> 3350 kcal
    # protein = 1.6 * 90 = 144 g ; fat = 0.40 * 3350 / 9 = 148.89 -> 149 g
    # carbs = (3350 - 576 - 1341) / 4 = 358.25 -> 358 g
    r = calculate_targets(TargetInputs("male", 40, 175, 90, "very", "gain", 0.25, "standard", "lower_carb"))
    assert r.daily_energy_change == 247.5
    assert (r.kcal, r.protein_g, r.fat_g, r.carb_g) == (3350, 144, 149, 358)


def test_case_d_unspecified_sex_uses_midpoint_offset():
    # BMR = 700 + 1062.5 - 175 - 78 = 1509.5 ; TDEE = 1509.5 * 1.375 = 2075.5625 -> 2080
    # protein = 1.6 * 70 = 112 g ; fat = 0.30 * 2080 / 9 = 69.33 -> 69 g
    # carbs = (2080 - 448 - 621) / 4 = 252.75 -> 253 g
    r = calculate_targets(TargetInputs("unspecified", 35, 170, 70, "light", "maintain"))
    assert r.bmr == 1509.5
    assert (r.kcal, r.protein_g, r.fat_g, r.carb_g) == (2080, 112, 69, 253)


def test_case_e_sex_minimum_beats_bmr():
    # BMR = 450 + 937.5 - 350 - 161 = 876.5 ; TDEE = 1051.8 ; deficit = 0.01*45*7700/7 = 495
    # 556.8 kcal -> far below the 1,200 kcal female minimum -> 1200
    # protein 1.6*45 = 72 g ; fat = 0.30*1200/9 = 40 g ; carbs = (1200 - 288 - 360)/4 = 138 g
    r = calculate_targets(TargetInputs("female", 70, 150, 45, "sedentary", "lose", 1.0))
    assert r.minimum_applied and r.minimum_kcal == 1200
    assert (r.kcal, r.protein_g, r.fat_g, r.carb_g) == (1200, 72, 40, 138)
    # at 1,200 kcal this person is above maintenance, and Venn says so
    assert r.estimated_weekly_change_kg > 0
    assert any("not below your estimated maintenance" in w for w in r.warnings)


def test_macros_always_add_up_to_calories():
    for sex in ("male", "female", "unspecified"):
        for goal, rate in (("lose", 1.0), ("maintain", 0), ("gain", 0.5)):
            for style in ("balanced", "lower_carb", "lower_fat"):
                r = calculate_targets(TargetInputs(sex, 45, 170, 75, "moderate", goal, rate, "very_high", style))
                assert abs(4 * r.protein_g + 4 * r.carb_g + 9 * r.fat_g - r.kcal) <= 6  # rounding only
                assert min(r.protein_g, r.carb_g, r.fat_g) >= 0


def test_round_half_up_is_not_bankers_rounding():
    assert round_half_up(252.5) == 253 and round_half_up(2085, 10) == 2090


# --- invalid inputs and safety constraints --------------------------------------------

@pytest.mark.parametrize("kwargs, message", [
    ({"age": 17}, "adults only"),
    ({"age": 101}, "adults only"),
    ({"height_cm": 100}, "height"),
    ({"weight_kg": 20}, "weight"),
    ({"goal": "lose", "goal_rate_pct": 1.5}, "between 0 and 1.0%"),
    ({"goal": "gain", "goal_rate_pct": 0.8}, "between 0 and 0.5%"),
    ({"goal": "maintain", "goal_rate_pct": 0.5}, "must be 0"),
    ({"goal": "lose", "goal_rate_pct": -0.5}, "between 0"),
    ({"sex": "robot"}, "sex"),
    ({"activity_level": "couch"}, "activity"),
])
def test_invalid_inputs_are_rejected(kwargs, message):
    base = dict(sex="male", age=30, height_cm=180, weight_kg=80, activity_level="moderate", goal="maintain")
    with pytest.raises(TargetInputError) as err:
        calculate_targets(TargetInputs(**{**base, **kwargs}))
    assert message in str(err.value)


def test_manual_targets_rules():
    assert validate_manual_targets(2000, 150, 200, 67, "female", 60) == []  # 600+800+603 = 2003
    assert any("at least 1200" in e for e in validate_manual_targets(900, 60, 100, 30, "female", 60))
    assert any("at least 1500" in e for e in validate_manual_targets(1400, 100, 150, 40, "male", 80))
    assert any("10%" in e for e in validate_manual_targets(2000, 50, 50, 20, "male", 80))
    assert any("4 g per kg" in e for e in validate_manual_targets(3000, 400, 200, 60, "male", 80))
    assert any("fat must be at least 20" in e for e in validate_manual_targets(1600, 150, 230, 10, "female", 60))
    assert any("at most 6000" in e for e in validate_manual_targets(7000, 300, 1000, 200, "male", 80))
