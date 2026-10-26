# Milestone 2: Nutrition Core

## Delivered

**Food catalog (offline).**
- 7,793 USDA SR Legacy foods with household portions, plus 20 barcoded packaged products from USDA Branded Foods. Sources and licences are in `data_sources.md`.
- The catalog is loaded into SQLite on first start, and again only when the bundled files change (checked by a content hash).
- Food ids are stable: rows are upserted by FDC id.

**Search.**
- Runs in memory, with no external API.
- Every query word must match a word in the food's name or brand. Matches in the first part of the name (before the first comma) rank higher.
- Two boosts:
  - a curated list of 67 everyday staples (so "egg" shows "Egg, whole, raw, fresh" first, not dried egg);
  - the user's recently logged foods.

**Units and math** (`services/nutrition.py`).
- Supported units:
  - mass: g, kg, oz, lb;
  - volume: ml, L, fl oz (for liquids);
  - USDA household portions;
  - label servings.
- Formula: value per 100 × quantity × unit size ÷ 100, rounded half-up to 0.1.
- Each entry stores a snapshot: the per-100 values and the unit sizes it was logged with. Edits recompute from the snapshot, so catalog updates never rewrite history.

**Food log.**
- Entries are stored with the local wall-clock time eaten (`eaten_at`, minute precision) and a `local_date`. There are no fixed meal slots.
- Multiple entries can share any time.
- Users can edit quantity, unit and time (which can move an entry to another day) and delete entries.
- Manual entries (description plus per-serving macros) are supported.
- Every query is filtered by the user from the session. Bodies with unknown fields, such as `user_id`, are rejected.

**Daily summary.**
- `/api/nutrition/day` returns entries in time order, totals, the target that was in effect on that date, and per-nutrient progress.
- Progress states: `no_target`, `empty`, `partial`, `met` (equal after rounding to whole units), `over`.
- `/api/nutrition/week` counts the days with food logged.

**Plausibility checks** (`services/plausibility.py`).
- **Errors (rejected):** quantity of 0 or less, or not a number; more than 25 kg or 30,000 kcal in one entry.
- **Warnings (HTTP 409, needing a fix or confirmation):**
  - 20 or more servings, with a "Did you mean N g?" fix (the "70,000 kcal" case from the audit);
  - large kg/lb/L numbers, with a smaller-unit fix;
  - more than 3 kg or 3,000 kcal in one entry;
  - a day above 10,000 kcal;
  - manual macros whose energy differs from the calories by more than 25% and more than 50 kcal.

**Barcodes.**
- Accepts UPC-A, EAN-13, EAN-8 and GTIN-14, with check-digit validation and zero-padding to GTIN-14.
- Recognised products show their nutrition before logging.
- Unknown codes get a clear message with **Search** and **Enter manually** buttons.
- Invalid codes get a specific error (wrong length, letters, or check digit).

**Camera and photo scanning.**
- Done in the browser with ZXing (MIT / Apache-2.0), loaded only when needed. The native `BarcodeDetector` is used when the browser has one. No external service is involved.

**Interface.**
- **Nutrition page:** day navigation, calorie and macro bars (filled = eaten, light shade = remaining, hatched orange = over target), and a time-ordered log.
- **Add food:** **+ Add food** on desktop; on phones, a round **+** at the bottom centre.
- **Add-food sheet:** Recent, Search, Barcode and Manual tabs, then a quantity step with a live preview, unit choice and date-time.
- **Edit sheet:** for any entry, with a two-step delete.
- **Home dashboard:** shows today's real totals and a 7-day logging strip.

**Pricing.**
- `ai/pricing.py` holds the professor's reference prices.
- The AI health check now also reports cache-write tokens and an estimated cost.
- Nutrition features make no model calls.

## Architecture decisions and adjustments

| Decision | Reason |
|---|---|
| Kept **username** login (no switch to email) | Milestone 1 uses usernames, and its 49 tests cover registration, login, throttling and isolation. Switching to email the day before the deadline would add migration risk and need email checks or recovery flows, which the brief says to avoid. An email field can be added later as an optional, unique column without breaking anything. |
| Branded products come from the USDA **bulk** download, not the API | `DEMO_KEY` returned HTTP 429 (about 10 requests per hour). The bulk file contains the same manufacturer-submitted data. |
| Barcodes come from USDA Branded Foods rather than Open Food Facts | Public domain, manufacturer-submitted, and no new dependency. Open Food Facts stays deferred (G6). |
| A wall-clock `eaten_at` with no time zone, plus `local_date` | "Breakfast at 07:45" stays 07:45 wherever the server is. Day views never shift because of UTC. The browser sends local time, and the server rejects time-zone-aware timestamps. |
| Search in memory instead of SQLite FTS5 | Avoids Alembic and virtual-table complications. About 7.8k foods index in under 100 ms and search in milliseconds. |
| Confirmation via HTTP 409 with suggestions | Saving stays a single step in the normal case. Only flagged entries need a second action, which is either a one-tap fix or "It's correct, save anyway". |
| Each day uses the target in effect on that date | Venn does not fill in a target for days before one existed. The demo account's first target is dated 30 days back so that its seeded history has targets. |

## Tests

- **Backend: 89 passed.** The 49 Milestone 1 tests still pass, and 40 are new. See `docs/evidence/m2_backend_tests.txt`.
- **Frontend: 28 passed** (8 from Milestone 1, 20 new). See `docs/evidence/m2_frontend_tests.txt`.

New test coverage:

- **Search:** real-catalog results, ranking, staples, and the recent-food boost.
- **Barcodes:** recognised, unknown (404), invalid check digit (422), the EAN-13 form of a UPC-A code, and GTIN-14.
- **Units:** conversions (g, oz, lb, kg, portions, servings, ml, fl oz) checked against hand calculations.
- **Entries:** create, edit (quantity, unit, time, moving to another day), delete, and manual entries.
- **Ordering and totals:** time order, daily totals and progress, week summary.
- **Targets and empty states:** empty day, no target, a date before the first target, and every progress state including "met" and "over".
- **Plausibility:** the servings-vs-grams fix, confirmation, hard errors, invalid units, time-zone-aware timestamps, unknown fields.
- **History:** stays the same after a catalog value changes.
- **Recent foods:** order and last quantity.
- **Isolation:** another user's entry ids return 404 for get, patch and delete, and their day, recent and week views are empty.
- **Persistence:** entries survive an app restart (two app instances on the same database file).
- **Demo seed:** runs only once.
- **Frontend:** bar-segment logic for every state, preview math, local-date handling, and the full UI flows (search → quantity → save with timestamp; recent re-use; plausibility warning plus the suggested fix; unknown barcode → manual entry; missing-target message; over-target text).

## Evidence

Screenshots were taken from the real app with demo data. `frontend/scripts/screenshots.mjs` recreates them.

| File | What it shows |
|---|---|
| `docs/evidence/m2_nutrition_dashboard_desktop.png` | Nutrition page: 1,044 of 2,320 kcal eaten, with 1,276 remaining; four macro bars (filled vs. shaded remaining); 7 entries in time order from 07:45 to 16:15 |
| `docs/evidence/m2_add_food_recent.png` | Add-food sheet, Recent tab: recently logged foods with their last quantity and kcal |
| `docs/evidence/m2_add_food_search.png` | Search for "chicken breast": USDA results with kcal per 100 g; the roasted breast ranks first |
| `docs/evidence/m2_add_food_quantity.png` | Quantity step: 150 g of chicken breast with a live preview (248 kcal, P 46.5 g), date-time and source |
| `docs/evidence/m2_barcode_lookup.png` | Typed UPC 888849009305 matched to the Quest bar, with its per-serving nutrition and FDC source |
| `docs/evidence/m2_barcode_photo_decoded.png` | **Scan from photo:** an EAN-13 image (Oreo 044000065713) decoded by ZXing in a real headless Chrome and matched in the catalog |
| `docs/evidence/m2_plausibility_warning.png` | 150 servings of the protein bar (28,530 kcal) is stopped, with "Did you mean 150 g?" and a one-tap fix |
| `docs/evidence/m2_home_dashboard_desktop.png` | Home dashboard: today's real totals and the 4/7 days-logged strip |
| `docs/evidence/m2_nutrition_mobile.png` | Phone layout: stacked summary, time-ordered log, bottom-centre **+** above the navigation bar |
| `docs/evidence/m2_add_food_mobile.png` | Phone layout: add-food bottom sheet with recent foods |
| `docs/evidence/m2_fresh_clone.txt` | Fresh-clone setup without a key or Node.js: 127 s to a running app with nutrition working |

## Known limitations

- **Camera scanning** (`getUserMedia` plus ZXing) is implemented but **not verified with a physical camera**; this machine's tests ran headless. Photo decoding and typed lookup are verified.
- **Barcode coverage** is only the 20 bundled products. There is no online lookup and no user-created barcode products yet.
- **Saved meals:** "frequently used foods" are covered by the Recent tab, but there are no saved multi-food meals or custom foods (manual entries are one-off).
- **USDA naming:** search follows USDA's wording, so some everyday terms (e.g. "tuna can") need USDA terms ("tuna, light, canned").
- **Liquids** in ml are not converted to grams. Generic liquids (milk) use USDA cup or fl oz portions measured in grams.
- **No undo** after deleting an entry (the delete needs a second click).
- **Day boundaries** follow the browser's local date. A user who changes time zones keeps the wall-clock times they entered.
