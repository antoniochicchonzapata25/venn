"""Nutrition Core through the API, on the real bundled USDA catalog (offline)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.models import Food
from tests.conftest import VALID_PROFILE, register

CHICKEN = "Chicken, broilers or fryers, breast, meat only, cooked, roasted"  # 165 kcal, 31.02 P, 0 C, 3.57 F
OREO_UPC = "044000065713"


def food_id(client: TestClient, query: str, name: str) -> int:
    results = client.get("/api/foods/search", params={"q": query, "limit": 50}).json()["results"]
    return next(r["id"] for r in results if r["name"] == name)


def add(client, fid, quantity, unit="g", at="2026-10-25T12:30", confirm=False, expect=201):
    r = client.post("/api/nutrition/entries", json={"food_id": fid, "quantity": quantity, "unit": unit,
                                                    "eaten_at": at, "confirm": confirm})
    assert r.status_code == expect, r.text
    return r.json()


# --- catalog ------------------------------------------------------------------------------

def test_search_needs_login_and_finds_usda_foods(client):
    assert client.get("/api/foods/search", params={"q": "chicken"}).status_code == 401
    register(client, "sam")
    res = client.get("/api/foods/search", params={"q": "chicken breast roasted"}).json()["results"]
    assert res and res[0]["name"] == CHICKEN
    top = res[0]
    assert top["per_100"] == {"kcal": 165.0, "protein_g": 31.02, "carb_g": 0.0, "fat_g": 3.57}
    assert "USDA" in top["source_label"]
    banana = client.get("/api/foods/search", params={"q": "banana"}).json()["results"][0]
    assert banana["name"] == "Bananas, raw"


def test_food_detail_lists_units_with_sizes(client):
    register(client, "tia")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    d = client.get(f"/api/foods/{fid}").json()
    units = {u["unit"]: u for u in d["units"]}
    assert {"g", "oz", "lb", "kg"} <= units.keys()
    cup = next(u for u in d["units"] if u["label"].startswith("1 cup"))
    assert cup["size"] == 140.0 and cup["kind"] == "count"
    assert d["source_ref"] == "171477"


def test_barcode_lookup_recognised_unknown_and_invalid(client):
    register(client, "uma")
    hit = client.get(f"/api/foods/barcode/{OREO_UPC}")
    assert hit.status_code == 200
    body = hit.json()
    assert body["brand"] == "Oreo" and body["barcode"] == OREO_UPC and body["source"] == "usda_branded"
    assert body["units"][0]["unit"] == "serving"
    # same product typed as EAN-13 with a leading zero
    assert client.get("/api/foods/barcode/0044000065713").json()["id"] == body["id"]
    # valid check digit, not in the sample
    miss = client.get("/api/foods/barcode/036000291452")
    assert miss.status_code == 404 and miss.json()["detail"]["code"] == "barcode_not_found"
    bad = client.get("/api/foods/barcode/044000065714")
    assert bad.status_code == 422 and "check digit" in bad.json()["detail"][0]
    assert len(client.get("/api/foods/barcodes").json()["products"]) >= 10


# --- entries ------------------------------------------------------------------------------

def test_create_entry_computes_and_stores_nutrition(client):
    register(client, "vic")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    e = add(client, fid, 150)
    assert (e["kcal"], e["protein_g"], e["carb_g"], e["fat_g"]) == (247.5, 46.5, 0.0, 5.4)
    assert e["eaten_at"] == "2026-10-25T12:30" and e["local_date"] == "2026-10-25"
    assert e["amount"] == 150 and e["unit_label"] == "g"
    oz = add(client, fid, 4, "oz", "2026-10-25T19:00")
    assert oz["kcal"] == 187.1 and oz["amount"] == 113.4


def test_day_is_chronological_and_totals_add_up(client):
    register(client, "wes")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    banana = food_id(client, "banana", "Bananas, raw")  # 89 kcal, 1.09 P, 22.84 C, 0.33 F per 100 g
    add(client, fid, 100, at="2026-10-25T19:15")
    add(client, banana, 118, at="2026-10-25T07:05")
    add(client, fid, 100, at="2026-10-25T12:00")
    add(client, banana, 100, at="2026-10-24T23:59")  # previous day
    day = client.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()
    assert [e["eaten_at"][-5:] for e in day["entries"]] == ["07:05", "12:00", "19:15"]
    # banana 118 g: 89*1.18 = 105.02 -> 105.0 kcal; chicken 2 x 165 = 330 -> total 435.0
    assert day["totals"]["kcal"] == 435.0
    assert day["totals"]["protein_g"] == round(1.3 + 31.0 + 31.0, 1)  # 1.09*1.18 = 1.2862 -> 1.3
    assert len(client.get("/api/nutrition/day", params={"date": "2026-10-24"}).json()["entries"]) == 1


def test_day_without_profile_has_no_target_and_empty_state(client):
    register(client, "xia")
    day = client.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()
    assert day["entries"] == [] and day["target"] is None
    assert day["progress"]["kcal"]["state"] == "no_target" and day["progress"]["kcal"]["remaining"] is None


def test_day_with_target_reports_progress(client):
    register(client, "yan")
    client.put("/api/profile", json=VALID_PROFILE)
    target = client.get("/api/targets/current").json()["target"]
    from datetime import date
    today = date.today().isoformat()
    empty = client.get("/api/nutrition/day", params={"date": today}).json()
    assert empty["target"]["kcal"] == target["kcal"] and empty["progress"]["kcal"]["state"] == "empty"
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    add(client, fid, 100, at=f"{today}T12:00")
    p = client.get("/api/nutrition/day", params={"date": today}).json()["progress"]
    assert p["kcal"]["state"] == "partial" and p["kcal"]["remaining"] == target["kcal"] - 165.0
    # a day before the target existed has no target (not back-filled)
    assert client.get("/api/nutrition/day", params={"date": "2020-01-01"}).json()["target"] is None


def test_edit_quantity_unit_and_time_then_delete(client):
    register(client, "zed")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    e = add(client, fid, 100, at="2026-10-25T12:00")
    r = client.patch(f"/api/nutrition/entries/{e['id']}", json={"quantity": 200}).json()
    assert r["kcal"] == 330.0 and r["eaten_at"] == "2026-10-25T12:00"
    r = client.patch(f"/api/nutrition/entries/{e['id']}", json={"eaten_at": "2026-10-23T08:15"}).json()
    assert r["local_date"] == "2026-10-23" and r["kcal"] == 330.0
    cup = next(u["unit"] for u in r["units"] if u["label"].startswith("1 cup"))
    r = client.patch(f"/api/nutrition/entries/{e['id']}", json={"quantity": 1, "unit": cup}).json()
    assert r["kcal"] == 231.0 and r["amount"] == 140.0  # 1 cup = 140 g -> 165*1.4
    assert client.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()["entries"] == []
    assert client.delete(f"/api/nutrition/entries/{e['id']}").status_code == 204
    assert client.get(f"/api/nutrition/entries/{e['id']}").status_code == 404


def test_implausible_quantity_needs_confirmation_or_correction(client):
    register(client, "abe")
    quest = client.get("/api/foods/barcode/888849009305").json()  # Quest bar, 60 g serving, 317 kcal/100 g
    r = add(client, quest["id"], 150, "serving", expect=409)
    detail = r["detail"]
    assert detail["code"] == "confirmation_required"
    assert detail["suggestions"][0]["unit"] == "g" and detail["preview"]["kcal"] == 28530.0
    # the user applies the suggested fix
    fixed = add(client, quest["id"], 150, "g")
    assert fixed["kcal"] == 475.5
    # or explicitly confirms an unusual but possible entry
    big = add(client, quest["id"], 1000, "g", expect=409)
    assert "3,170 kcal" in " ".join(big["detail"]["warnings"])
    assert add(client, quest["id"], 1000, "g", confirm=True)["kcal"] == 3170.0
    # impossible amounts are rejected even with confirm
    assert add(client, quest["id"], 30, "kg", confirm=True, expect=422)


def test_invalid_input_is_rejected(client):
    register(client, "bea")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    add(client, fid, 0, expect=422)
    add(client, fid, -3, expect=422)
    add(client, fid, 100, unit="teaspoon", expect=422)
    add(client, fid, 100, at="2026-10-25T12:00:00+02:00", expect=422)  # local time only
    add(client, fid, 100, at="1990-01-01T12:00", expect=422)
    add(client, 999_999, 100, expect=404)
    r = client.post("/api/nutrition/entries", json={"food_id": fid, "quantity": 1, "unit": "g",
                                                    "eaten_at": "2026-10-25T12:00", "user_id": 2})
    assert r.status_code == 422  # no user_id smuggling


def test_manual_entry_and_macro_check(client):
    register(client, "cal")
    base = {"description": "Homemade lasagna", "kcal": 450, "protein_g": 25, "carb_g": 40, "fat_g": 20,
            "eaten_at": "2026-10-25T20:00"}  # 100+160+180 = 440 kcal, consistent
    r = client.post("/api/nutrition/entries/manual", json=base)
    assert r.status_code == 201 and r.json()["kind"] == "manual" and r.json()["kcal"] == 450
    r = client.post("/api/nutrition/entries/manual", json={**base, "kcal": 1500})
    assert r.status_code == 409 and "add up to about 440 kcal" in r.json()["detail"]["warnings"][0]
    edited = client.patch(f"/api/nutrition/entries/{client.get('/api/nutrition/day', params={'date': '2026-10-25'}).json()['entries'][0]['id']}",
                          json={"quantity": 2}).json()
    assert edited["kcal"] == 900


def test_history_is_stable_when_catalog_values_change(client, app):
    register(client, "dee")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    e = add(client, fid, 100)
    with app.state.session_factory() as db:  # simulate a catalog update (e.g. a newer USDA release)
        db.execute(update(Food).where(Food.id == fid).values(kcal_100=999.0))
        db.commit()
        assert db.scalar(select(Food.kcal_100).where(Food.id == fid)) == 999.0
    day = client.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()
    assert day["entries"][0]["kcal"] == 165.0
    # editing the old entry recomputes from the values it was logged with
    assert client.patch(f"/api/nutrition/entries/{e['id']}", json={"quantity": 200}).json()["kcal"] == 330.0
    # new entries use the new catalog value
    assert add(client, fid, 100)["kcal"] == 999.0


def test_recent_foods_most_recent_first_with_last_quantity(client):
    register(client, "eli")
    chicken = food_id(client, "chicken breast roasted", CHICKEN)
    banana = food_id(client, "banana", "Bananas, raw")
    add(client, chicken, 100, at="2026-10-24T12:00")
    add(client, banana, 118, at="2026-10-25T08:00")
    add(client, chicken, 175, at="2026-10-23T12:00")  # logged last (a past meal), so most recent use
    recent = client.get("/api/foods/recent").json()["results"]
    assert [r["id"] for r in recent] == [chicken, banana]
    assert recent[0]["times_logged"] == 2 and recent[0]["last"]["quantity"] == 175
    # search boosts the user's recent foods
    assert client.get("/api/foods/search", params={"q": "chicken"}).json()["results"][0]["id"] == chicken


def test_week_summary_counts_logged_days(client):
    register(client, "fay")
    fid = food_id(client, "chicken breast roasted", CHICKEN)
    for d in ("2026-10-19", "2026-10-21", "2026-10-25", "2026-10-25"):
        add(client, fid, 100, at=f"{d}T12:00")
    w = client.get("/api/nutrition/week", params={"end": "2026-10-25"}).json()
    assert w["days_logged"] == 3 and w["days"][-1]["kcal"] == 330.0 and len(w["days"]) == 7


# --- isolation and persistence -------------------------------------------------------------

def test_entries_are_isolated_between_users(two_users):
    alice, bob = two_users
    fid = food_id(alice, "chicken breast roasted", CHICKEN)
    e = add(alice, fid, 100)
    assert bob.get(f"/api/nutrition/entries/{e['id']}").status_code == 404
    assert bob.patch(f"/api/nutrition/entries/{e['id']}", json={"quantity": 1}).status_code == 404
    assert bob.delete(f"/api/nutrition/entries/{e['id']}").status_code == 404
    assert bob.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()["entries"] == []
    assert bob.get("/api/foods/recent").json()["results"] == []
    assert bob.get("/api/nutrition/week", params={"end": "2026-10-25"}).json()["days_logged"] == 0
    assert alice.get(f"/api/nutrition/entries/{e['id']}").json()["quantity"] == 100


def test_entries_survive_an_app_restart(db_url, tmp_path):
    from app.main import create_app

    with TestClient(create_app(database_url=db_url, frontend_dist=tmp_path / "x")) as c:
        register(c, "gus")
        fid = food_id(c, "chicken breast roasted", CHICKEN)
        add(c, fid, 120)
    with TestClient(create_app(database_url=db_url, frontend_dist=tmp_path / "x")) as c2:
        assert c2.post("/api/auth/login", json={"username": "gus", "password": "correct-horse-1"}).status_code == 200
        entries = c2.get("/api/nutrition/day", params={"date": "2026-10-25"}).json()["entries"]
        assert len(entries) == 1 and entries[0]["kcal"] == 198.0


def test_demo_seed_creates_a_week_of_entries(client, app):
    from app.seed import ensure_demo_nutrition, ensure_demo_user

    with app.state.session_factory() as db:
        ensure_demo_user(db)
        assert ensure_demo_nutrition(db) >= 20
        assert ensure_demo_nutrition(db) == 0  # idempotent
    client.post("/api/auth/login", json={"username": "demo", "password": "venn-demo-2026"})
    from datetime import date
    day = client.get("/api/nutrition/day", params={"date": date.today().isoformat()}).json()
    assert len(day["entries"]) >= 5 and day["target"] is not None
    assert day["totals"]["kcal"] == round(sum(e["kcal"] for e in day["entries"]), 1)


def test_target_day_boundary_uses_the_users_time_zone(client, app):
    """Regression: a target set at 20:00 in New York (01:00 UTC next day) applies to that New York day."""
    from datetime import datetime

    from app.models import NutritionTarget

    register(client, "tzz")
    client.put("/api/profile", json=VALID_PROFILE)
    with app.state.session_factory() as db:
        db.execute(update(NutritionTarget).values(created_at=datetime(2026, 10, 26, 1, 0)))  # stored as UTC
        db.commit()
    ny = {"tz_offset": 300}  # UTC-5: getTimezoneOffset() = 300
    assert client.get("/api/nutrition/day", params={"date": "2026-10-25", **ny}).json()["target"] is not None
    assert client.get("/api/nutrition/day", params={"date": "2026-10-24", **ny}).json()["target"] is None
    utc = {"tz_offset": 0}
    assert client.get("/api/nutrition/day", params={"date": "2026-10-25", **utc}).json()["target"] is None
