"""Load the bundled USDA food catalog into SQLite (offline) and keep a search index in memory.

The catalog files live in backend/app/data/ and are built by scripts/build_food_catalog.py.
Loading is idempotent and keyed by a content hash: it runs on first start and again only
when the bundled files change. Food rows are upserted by (source, source_ref), so food ids
stay stable; logged entries keep their own nutrition snapshot either way.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import threading
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import AppMeta, Food, FoodPortion
from app.services import food_search
from app.services.barcode import BarcodeError, normalize

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SR_FILE = DATA_DIR / "usda_sr_legacy.json.gz"
BRANDED_FILE = DATA_DIR / "usda_branded_sample.json"
STAPLES_FILE = DATA_DIR / "staple_foods.json"
META_KEY = "food_catalog_version"

SOURCE_LABELS = {
    "usda_sr_legacy": "USDA FoodData Central, SR Legacy",
    "usda_branded": "USDA FoodData Central, Branded Foods (manufacturer label)",
}


def catalog_version() -> str:
    h = hashlib.sha256()
    for f in (SR_FILE, BRANDED_FILE):
        h.update(f.read_bytes() if f.is_file() else b"-")
    return h.hexdigest()[:16]


def _records() -> tuple[list[dict], list[tuple[str, str, list[dict]]]]:
    foods, portions = [], []
    if SR_FILE.is_file():
        with gzip.open(SR_FILE, "rt", encoding="utf-8") as fh:
            sr = json.load(fh)
        for f in sr["foods"]:
            ref = str(f["fdc_id"])
            foods.append(dict(source="usda_sr_legacy", source_ref=ref, name=f["name"], brand="",
                              category=f.get("category", ""), barcode=None, basis="g",
                              kcal_100=f["kcal"], protein_100=f["protein"], carb_100=f["carb"], fat_100=f["fat"],
                              serving_size=None, serving_label="", published=f.get("published", "")))
            portions.append(("usda_sr_legacy", ref, f.get("portions", [])))
    if BRANDED_FILE.is_file():
        branded = json.loads(BRANDED_FILE.read_text(encoding="utf-8"))
        for p in branded["products"]:
            try:
                barcode = normalize(p["barcode"])
            except BarcodeError:
                continue
            foods.append(dict(source="usda_branded", source_ref=str(p["fdc_id"]), name=p["name"], brand=p.get("brand", ""),
                              category=p.get("category", ""), barcode=barcode, basis=p.get("basis", "g"),
                              kcal_100=p["kcal"], protein_100=p["protein"], carb_100=p["carb"], fat_100=p["fat"],
                              serving_size=p.get("serving_size"), serving_label=p.get("serving_label", ""),
                              published=p.get("published", "")))
    return foods, portions


def ensure_catalog(db: Session) -> bool:
    """Load or refresh the catalog if the bundled files changed. Returns True if it loaded."""
    version = catalog_version()
    meta = db.get(AppMeta, META_KEY)
    if meta is not None and meta.value == version:
        return False
    foods, portions = _records()
    for i in range(0, len(foods), 500):
        chunk = foods[i:i + 500]
        stmt = sqlite_insert(Food).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "source_ref"],
            set_={c: stmt.excluded[c] for c in chunk[0] if c not in ("source", "source_ref")},
        )
        db.execute(stmt)
    ids = {(s, r): i for i, s, r in db.execute(select(Food.id, Food.source, Food.source_ref))}
    catalog_ids = [ids[(s, r)] for s, r, _ in portions if (s, r) in ids]
    for i in range(0, len(catalog_ids), 900):
        db.execute(delete(FoodPortion).where(FoodPortion.food_id.in_(catalog_ids[i:i + 900])))
    rows = [
        {"food_id": ids[(s, r)], "seq": n, "label": p["label"], "amount": p["grams"]}
        for s, r, plist in portions if (s, r) in ids for n, p in enumerate(plist)
    ]
    for i in range(0, len(rows), 2000):
        db.execute(FoodPortion.__table__.insert(), rows[i:i + 2000])
    if meta is None:
        db.add(AppMeta(key=META_KEY, value=version))
    else:
        meta.value = version
    db.commit()
    _INDEX_CACHE.clear()
    return True


_INDEX_CACHE: dict[str, list[food_search.IndexedFood]] = {}
_INDEX_LOCK = threading.Lock()


def search_index(db: Session) -> list[food_search.IndexedFood]:
    key = str(db.get_bind().url)
    with _INDEX_LOCK:
        if key not in _INDEX_CACHE:
            staples = frozenset(json.loads(STAPLES_FILE.read_text(encoding="utf-8"))["names"]) if STAPLES_FILE.is_file() else frozenset()
            _INDEX_CACHE[key] = food_search.build_index(db.execute(select(Food.id, Food.name, Food.brand)), staples)
        return _INDEX_CACHE[key]


def clear_index_cache() -> None:
    _INDEX_CACHE.clear()
