"""Pure nutrition logic: unit conversion, per-entry math, totals, progress states,
plausibility rules, barcode validation, search ranking and reference pricing.
Expected values are worked out by hand in the comments."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.ai.pricing import estimate_cost_usd
from app.services import barcode, food_search, nutrition
from app.services.plausibility import assess_catalog_entry, assess_manual_entry

CHICKEN = {"kcal": 165.0, "protein_g": 31.02, "carb_g": 0.0, "fat_g": 3.57}  # USDA SR 171477, per 100 g


# --- units and per-entry math ----------------------------------------------------------

def test_nutrition_for_grams():
    # 150 g: 165*1.5 = 247.5 kcal; 31.02*1.5 = 46.53 -> 46.5; 3.57*1.5 = 5.355 -> 5.4 (half up)
    assert nutrition.nutrition_for(CHICKEN, 150) == {"kcal": 247.5, "protein_g": 46.5, "carb_g": 0.0, "fat_g": 5.4}


@pytest.mark.parametrize("unit, quantity, grams", [
    ("oz", 4, 113.39809), ("lb", 0.5, 226.796185), ("kg", 0.2, 200.0), ("g", 75, 75.0),
])
def test_mass_units_convert_to_grams(unit, quantity, grams):
    assert math.isclose(quantity * nutrition.GRAMS_PER[unit], grams, rel_tol=1e-6)


def test_unit_options_and_snapshot_recompute():
    food = SimpleNamespace(basis="g", serving_size=None, serving_label="", portions=[
        SimpleNamespace(id=7, label="1 cup, chopped or diced", amount=140.0)],
        kcal_100=165.0, protein_100=31.02, carb_100=0.0, fat_100=3.57, source="usda_sr_legacy", source_ref="171477")
    opts = nutrition.unit_options(food)
    assert [o.unit for o in opts] == ["portion:7", "g", "kg", "oz", "lb"]
    snap = nutrition.basis_snapshot(food, opts)
    # 1.5 cups = 210 g -> 165*2.1 = 346.5 kcal; 4 oz = 113.398 g -> 187.107 -> 187.1 kcal
    values, amount, label, kind = nutrition.compute_entry(snap, 1.5, "portion:7")
    assert (values["kcal"], amount, kind) == (346.5, 210.0, "count") and label.startswith("1 cup")
    assert nutrition.compute_entry(snap, 4, "oz")[0]["kcal"] == 187.1
    with pytest.raises(KeyError):
        nutrition.compute_entry(snap, 1, "teaspoon")


def test_liquid_units_and_servings():
    milk = SimpleNamespace(basis="ml", serving_size=240.0, serving_label="1 cup", portions=[],
                           kcal_100=58.0, protein_100=5.42, carb_100=5.42, fat_100=1.88, source="usda_branded", source_ref="1")
    opts = nutrition.unit_options(milk)
    assert [o.unit for o in opts] == ["serving", "ml", "l", "fl_oz"]
    snap = nutrition.basis_snapshot(milk, opts)
    # 1 serving = 240 ml -> 58*2.4 = 139.2 kcal; 8 fl oz = 236.588 ml -> 137.2 kcal
    assert nutrition.compute_entry(snap, 1, "serving")[0]["kcal"] == 139.2
    assert nutrition.compute_entry(snap, 8, "fl_oz")[0]["kcal"] == 137.2


def test_manual_snapshot_scales_per_serving():
    snap = nutrition.manual_snapshot({"kcal": 250, "protein_g": 10, "carb_g": 30, "fat_g": 10})
    values, amount, _, _ = nutrition.compute_entry(snap, 1.5, "serving")
    assert values == {"kcal": 375.0, "protein_g": 15.0, "carb_g": 45.0, "fat_g": 15.0} and amount is None


def test_totals_sum_stored_values():
    entries = [SimpleNamespace(kcal=247.5, protein_g=46.5, carb_g=0.0, fat_g=5.4),
               SimpleNamespace(kcal=205.4, protein_g=4.3, carb_g=44.5, fat_g=0.4)]
    assert nutrition.totals(entries) == {"kcal": 452.9, "protein_g": 50.8, "carb_g": 44.5, "fat_g": 5.8}
    assert nutrition.totals([]) == {"kcal": 0.0, "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0}


# --- progress states --------------------------------------------------------------------

@pytest.mark.parametrize("consumed, target, state, remaining, over", [
    (0, 2000, "empty", 2000, 0),
    (1240.4, 2000, "partial", 759.6, 0),
    (2000.4, 2000, "met", 0, 0.4),      # displays as 2000 / 2000
    (1999.6, 2000, "met", 0.4, 0),
    (2350, 2000, "over", 0, 350),
    (500, None, "no_target", None, None),
])
def test_progress_states(consumed, target, state, remaining, over):
    p = nutrition.progress(consumed, target)
    assert p["state"] == state and p["remaining"] == remaining and p["over"] == over
    if target:
        assert p["percent"] == round(consumed / target * 100, 1)


# --- plausibility -----------------------------------------------------------------------

def test_typing_grams_into_servings_is_flagged_with_a_fix():
    # 150 "servings" of a 40 g bar = 6,000 g, 25,500 kcal: the classic logging mistake
    a = assess_catalog_entry(150, "serving", "count", "g", 6000, 25_500, 0)
    assert not a.errors
    assert any("Did you mean 150 g" in w for w in a.warnings)
    assert a.suggestions[0] == {"quantity": 150, "unit": "g", "label": "Use 150 g instead"}


def test_normal_and_large_but_real_meals_pass():
    assert assess_catalog_entry(200, "g", "mass", "g", 200, 330, 1500).warnings == []
    assert assess_catalog_entry(2, "serving", "count", "g", 120, 600, 0).warnings == []
    big = assess_catalog_entry(1200, "g", "mass", "g", 1200, 2400, 0)  # a large but plausible meal
    assert not big.errors and not big.warnings


def test_hard_errors():
    assert assess_catalog_entry(0, "g", "mass", "g", 0, 0, 0).errors
    assert assess_catalog_entry(-5, "g", "mass", "g", -5, 0, 0).errors
    assert assess_catalog_entry(float("nan"), "g", "mass", "g", 0, 0, 0).errors
    assert assess_catalog_entry(30, "kg", "mass", "g", 30_000, 50_000, 0).errors


def test_warnings_for_big_entries_units_and_days():
    assert any("Did you mean 8 g" in w for w in assess_catalog_entry(8, "kg", "mass", "g", 8000, 1000, 0).warnings)
    assert any("3,500 kcal" in w for w in assess_catalog_entry(700, "g", "mass", "g", 700, 3500, 0).warnings)
    assert any("day totals" in w for w in assess_catalog_entry(100, "g", "mass", "g", 100, 500, 9800).warnings)


def test_manual_entry_rules():
    ok = assess_manual_entry(1, {"kcal": 250, "protein_g": 10, "carb_g": 30, "fat_g": 10}, 0)  # 40+120+90 = 250
    assert not ok.errors and not ok.warnings
    mismatch = assess_manual_entry(1, {"kcal": 900, "protein_g": 10, "carb_g": 30, "fat_g": 10}, 0)
    assert any("add up to about 250 kcal" in w for w in mismatch.warnings)
    assert assess_manual_entry(1, {"kcal": -1, "protein_g": 0, "carb_g": 0, "fat_g": 0}, 0).errors
    assert assess_manual_entry(100, {"kcal": 500, "protein_g": 0, "carb_g": 0, "fat_g": 0}, 0).errors  # 50,000 kcal


# --- barcodes ---------------------------------------------------------------------------

def test_barcode_normalisation_and_check_digits():
    assert barcode.normalize("044000065713") == "00044000065713"      # UPC-A (Oreo, USDA sample)
    assert barcode.normalize("0 44000-06571 3") == "00044000065713"   # spaces and dashes are ignored
    assert barcode.normalize("96385074") == "00000096385074"          # EAN-8
    assert barcode.normalize("10016000322629") == "10016000322629"    # GTIN-14
    for bad, msg in [("044000065714", "check digit"), ("12345", "8, 12, 13 or 14"), ("abc123456789", "digits only")]:
        with pytest.raises(barcode.BarcodeError, match=msg):
            barcode.normalize(bad)


# --- search ranking -----------------------------------------------------------------------

def test_search_ranks_simple_matches_first():
    idx = food_search.build_index([
        (1, "Chicken, broilers or fryers, breast, meat only, cooked, roasted", ""),
        (2, "Soup, chicken noodle, canned, condensed", ""),
        (3, "Bananas, raw", ""),
        (4, "Banana chips", ""),
        (5, "CHOCOLATE CHIP COOKIE DOUGH PROTEIN BARS", "Quest"),
        (6, "Rice, white, cooked", ""),
        (7, "Rice, brown, cooked", ""),
    ], staple_names=frozenset({"Bananas, raw"}))
    assert food_search.search(idx, "chicken breast")[0] == 1
    assert 2 not in food_search.search(idx, "chicken breast")
    assert food_search.search(idx, "banana")[0] == 3
    assert food_search.search(idx, "quest bar") == [5]
    assert food_search.search(idx, "zzzz") == [] and food_search.search(idx, "  ") == []
    assert food_search.search(idx, "rice")[0] == 6                                # tie -> lower id
    assert food_search.search(idx, "rice", boost_ids=frozenset({7}))[0] == 7     # recently logged wins
    assert food_search.search(idx, "banana")[1] == 4                             # staple first, then others


# --- reference pricing ------------------------------------------------------------------------

def test_reference_cost_estimates():
    # luna: 11 input x $0.10/M + 5 output x $0.50/M = 0.0000011 + 0.0000025
    assert estimate_cost_usd("gpt-6-luna", 11, 0, 0, 5) == pytest.approx(3.6e-6)
    # 1,000 input of which 800 cached: 200 x 0.10 + 800 x 0.01 = 28 per M -> 0.000028 ; + 100 output x 0.5 = 0.00005
    assert estimate_cost_usd("gpt-6-luna", 1000, 800, 0, 100) == pytest.approx(7.8e-5)
    assert estimate_cost_usd("gpt-6-astra", 1_000_000, 0, 0, 0) == pytest.approx(10.0)
    assert estimate_cost_usd("unknown-model", 10, 0, 0, 10) is None
