"""Build Venn's bundled offline food catalog from USDA FoodData Central (public domain).

This is a one-time, reproducible build step. The app itself never downloads anything:
it reads the files this script writes to backend/app/data/.

1. Generic foods: USDA SR Legacy (April 2018 release) CSV download.
       python scripts/build_food_catalog.py sr-legacy path/to/FoodData_Central_sr_legacy_food_csv_2018-04.zip
   Download: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip

2. Packaged products with barcodes: USDA Branded Foods (manufacturer-submitted label data).
   Preferred: the bulk CSV (about 450 MB zip), filtered to a small curated sample:
       python scripts/build_food_catalog.py branded-bulk path/to/FoodData_Central_branded_food_csv_2026-04-30.zip
   Download: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_branded_food_csv_2026-04-30.zip
   Alternative: the FoodData Central search API (DEMO_KEY allows only ~10 requests/hour):
       python scripts/build_food_catalog.py branded [--api-key DEMO_KEY]

Only foods with all four core values (energy kcal, protein, carbohydrate, fat) are kept,
so the app never has to guess a missing value.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "backend" / "app" / "data"
ENERGY, PROTEIN, CARB, FAT = 1008, 1003, 1005, 1004
CORE = (ENERGY, PROTEIN, CARB, FAT)

# Branded search queries: common packaged foods people log often.
# (DEMO_KEY allows about 10 requests per hour, so the list is kept short.)
BRANDED_QUERIES = [
    "cheerios", "greek yogurt plain", "peanut butter creamy", "protein bar",
    "old fashioned oats", "almond milk unsweetened", "hummus", "tortilla chips",
]


def _csv_rows(z: zipfile.ZipFile, name: str):
    member = next(n for n in z.namelist() if n.endswith("/" + name))
    with z.open(member) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))


def build_sr_legacy(zip_path: Path) -> Path:
    z = zipfile.ZipFile(zip_path)
    categories = {r["id"]: r["description"] for r in _csv_rows(z, "food_category.csv")}
    units = {r["id"]: r["name"] for r in _csv_rows(z, "measure_unit.csv")}
    foods = {
        r["fdc_id"]: {"fdc_id": int(r["fdc_id"]), "name": r["description"].strip(),
                      "category": categories.get(r["food_category_id"], ""), "published": r["publication_date"]}
        for r in _csv_rows(z, "food.csv")
    }
    values: dict[str, dict[int, float]] = {}
    for r in _csv_rows(z, "food_nutrient.csv"):
        nid = int(r["nutrient_id"])
        if nid in CORE and r["amount"] != "":
            values.setdefault(r["fdc_id"], {})[nid] = float(r["amount"])
    portions: dict[str, list[dict]] = {}
    for r in _csv_rows(z, "food_portion.csv"):
        grams = float(r["gram_weight"] or 0)
        amount = float(r["amount"] or 0) or 1.0
        if grams <= 0:
            continue
        unit = units.get(r["measure_unit_id"], "")
        unit = "" if unit == "undetermined" else unit
        text = " ".join(p for p in (f"{amount:g}", unit, r["modifier"].strip() or r["portion_description"].strip()) if p)
        portions.setdefault(r["fdc_id"], []).append({"label": text, "grams": round(grams, 2), "seq": int(r["seq_num"] or 0)})

    out, skipped = [], 0
    for fid, food in foods.items():
        v = values.get(fid, {})
        if not all(k in v for k in CORE):
            skipped += 1
            continue
        food.update(kcal=v[ENERGY], protein=v[PROTEIN], carb=v[CARB], fat=v[FAT])
        food["portions"] = [{"label": p["label"], "grams": p["grams"]}
                            for p in sorted(portions.get(fid, []), key=lambda p: p["seq"])]
        out.append(food)
    out.sort(key=lambda f: f["fdc_id"])
    payload = {
        "source": "USDA FoodData Central, SR Legacy (April 2018), public domain",
        "source_url": "https://fdc.nal.usda.gov/download-datasets",
        "basis": "per 100 g",
        "foods": out,
        "skipped_missing_core_values": skipped,
    }
    path = OUT_DIR / "usda_sr_legacy.json.gz"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"wrote {path} with {len(out)} foods ({skipped} skipped: missing one of kcal/protein/carb/fat)")
    return path


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Venn-catalog-builder/1.0 (MGT 409 student project)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search_url(query: str, api_key: str) -> str:
    return "https://api.nal.usda.gov/fdc/v1/foods/search?" + urllib.parse.urlencode(
        {"query": query, "dataType": "Branded", "pageSize": 25, "api_key": api_key})


def build_branded(api_key: str, per_query: int = 4, from_dir: Path | None = None) -> Path:
    """Fetch (or, with from_dir, read previously saved) search responses: one <n>.json per query."""
    products, seen = [], set()
    for i, q in enumerate(BRANDED_QUERIES):
        try:
            if from_dir is not None:
                saved = from_dir / f"{i}.json"
                if not saved.is_file():
                    print(f"{q!r}: no saved response; skipped")
                    continue
                data = json.loads(saved.read_text(encoding="utf-8"))
            else:
                data = _get(search_url(q, api_key))
        except (urllib.error.HTTPError, json.JSONDecodeError) as error:
            print(f"{q!r}: {error}; skipped")
            continue
        taken = 0
        for f in data.get("foods", []):
            gtin = (f.get("gtinUpc") or "").strip()
            nutr = {n.get("nutrientId"): n.get("value") for n in f.get("foodNutrients", [])}
            unit = (f.get("servingSizeUnit") or "").lower()
            if not gtin.isdigit() or gtin in seen or not all(nutr.get(k) is not None for k in CORE):
                continue
            if unit not in ("g", "grm", "ml", "mlt") or not f.get("servingSize"):
                continue
            seen.add(gtin)
            products.append({
                "fdc_id": f["fdcId"], "barcode": gtin, "name": f.get("description", "").strip(),
                "brand": (f.get("brandName") or f.get("brandOwner") or "").strip(),
                "category": f.get("foodCategory", ""), "published": f.get("publishedDate", ""),
                "basis": "ml" if unit in ("ml", "mlt") else "g",
                "serving_size": float(f["servingSize"]),
                "serving_label": (f.get("householdServingFullText") or "").strip(),
                "kcal": nutr[ENERGY], "protein": nutr[PROTEIN], "carb": nutr[CARB], "fat": nutr[FAT],
            })
            taken += 1
            if taken >= per_query:
                break
        print(f"{q!r}: {taken} products")
        if from_dir is None:
            time.sleep(1.0)
    payload = {
        "source": "USDA FoodData Central, Branded Foods (manufacturer label data via GS1/Label Insight), public domain",
        "source_url": "https://fdc.nal.usda.gov/api-guide",
        "basis": "per 100 g or 100 ml (FDC normalises branded label values to 100 units)",
        "retrieved": time.strftime("%Y-%m-%d"),
        "products": products,
    }
    path = OUT_DIR / "usda_branded_sample.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} with {len(products)} products")
    return path


# (brand text, description text) pairs for the curated barcode sample; up to 2 products each.
BRANDED_PICKS = [
    ("CHEERIOS", "CHEERIOS"), ("CHOBANI", "GREEK"), ("FAIRLIFE", "MILK"), ("QUAKER", "OLD FASHIONED"),
    ("KIND", "BAR"), ("CLIF", "BAR"), ("NATURE VALLEY", "GRANOLA"), ("SKIPPY", "PEANUT BUTTER"),
    ("JIF", "PEANUT BUTTER"), ("OREO", "COOKIE"), ("COCA-COLA", "COCA-COLA"), ("SILK", "ALMOND"),
    ("SABRA", "HUMMUS"), ("TOSTITOS", "TORTILLA"), ("NUTELLA", "HAZELNUT"), ("BARILLA", "SPAGHETTI"),
    ("QUEST", "BAR"), ("GATORADE", "THIRST"), ("SIGGI", "YOGURT"), ("BEN & JERRY", "ICE CREAM"),
]


def gtin_check_ok(code: str) -> bool:
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def build_branded_bulk(zip_path: Path, per_pick: int = 2) -> Path:
    z = zipfile.ZipFile(zip_path)
    candidates: dict[int, list[dict]] = {i: [] for i in range(len(BRANDED_PICKS))}
    for r in _csv_rows(z, "branded_food.csv"):
        if r["discontinued_date"] or r["market_country"] not in ("", "United States"):
            continue
        gtin = r["gtin_upc"].strip()
        unit = r["serving_size_unit"].strip().lower()
        if not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14) or not gtin_check_ok(gtin):
            continue
        if unit not in ("g", "ml") or not r["serving_size"]:
            continue
        brand = f"{r['brand_name']} {r['brand_owner']} {r['subbrand_name']}".upper()
        text = f"{r['short_description']} {r['branded_food_category']}".upper()
        for i, (b, d) in enumerate(BRANDED_PICKS):
            if b in brand and (d in text or d in r["brand_name"].upper()):
                candidates[i].append({"fdc_id": r["fdc_id"], "gtin": gtin, "unit": unit,
                                      "serving_size": float(r["serving_size"]),
                                      "serving_label": r["household_serving_fulltext"].strip(),
                                      "brand": (r["brand_name"] or r["brand_owner"]).strip().title(),
                                      "category": r["branded_food_category"], "available": r["available_date"]})
                break
    wanted: dict[str, dict] = {}
    for i, rows in candidates.items():
        rows.sort(key=lambda c: c["available"], reverse=True)
        for c in rows[: per_pick * 6]:  # extra candidates in case some lack nutrients or a description
            wanted.setdefault(c["fdc_id"], {**c, "pick": i})
    names = {}
    for r in _csv_rows(z, "food.csv"):
        if r["fdc_id"] in wanted:
            names[r["fdc_id"]] = r["description"].strip()
    values: dict[str, dict[int, float]] = {}
    for r in _csv_rows(z, "food_nutrient.csv"):
        if r["fdc_id"] in wanted:
            nid = int(r["nutrient_id"])
            if nid in CORE and r["amount"] != "":
                values.setdefault(r["fdc_id"], {})[nid] = float(r["amount"])
    products, per_pick_count, seen = [], {}, set()
    for fid, c in sorted(wanted.items(), key=lambda kv: (kv[1]["pick"], kv[1]["available"]), reverse=False):
        v = values.get(fid, {})
        if not all(k in v for k in CORE) or fid not in names or c["gtin"] in seen:
            continue
        if per_pick_count.get(c["pick"], 0) >= per_pick:
            continue
        per_pick_count[c["pick"]] = per_pick_count.get(c["pick"], 0) + 1
        seen.add(c["gtin"])
        products.append({
            "fdc_id": int(fid), "barcode": c["gtin"], "name": names[fid], "brand": c["brand"],
            "category": c["category"], "published": c["available"], "basis": c["unit"],
            "serving_size": c["serving_size"], "serving_label": c["serving_label"],
            "kcal": v[ENERGY], "protein": v[PROTEIN], "carb": v[CARB], "fat": v[FAT],
        })
    payload = {
        "source": "USDA FoodData Central, Branded Foods (April 2026 release; manufacturer label data), public domain",
        "source_url": "https://fdc.nal.usda.gov/download-datasets",
        "basis": "per 100 g or 100 ml (FDC normalises branded label values to 100 units)",
        "retrieved": time.strftime("%Y-%m-%d"),
        "products": products,
    }
    path = OUT_DIR / "usda_branded_sample.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} with {len(products)} products")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sr = sub.add_parser("sr-legacy")
    sr.add_argument("zip_path", type=Path)
    br = sub.add_parser("branded")
    br.add_argument("--api-key", default="DEMO_KEY")
    br.add_argument("--from-dir", type=Path, help="read saved search responses (0.json, 1.json, ...) instead of fetching")
    bulk = sub.add_parser("branded-bulk")
    bulk.add_argument("zip_path", type=Path)
    urls = sub.add_parser("branded-urls", help="print the search URLs (to fetch with another tool)")
    urls.add_argument("--api-key", default="DEMO_KEY")
    args = parser.parse_args()
    if args.cmd == "sr-legacy":
        build_sr_legacy(args.zip_path)
    elif args.cmd == "branded-bulk":
        build_branded_bulk(args.zip_path)
    elif args.cmd == "branded-urls":
        for i, q in enumerate(BRANDED_QUERIES):
            print(i, search_url(q, args.api_key))
    else:
        build_branded(args.api_key, from_dir=args.from_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
