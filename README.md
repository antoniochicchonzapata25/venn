# Venn

**Venn** is a fitness and nutrition web app. It brings nutrition targets, workout planning and logging, body measurements, and AI progress insights into one adaptive plan. The plan is built around what you actually do, the equipment and time you have, and limitations you report yourself.

MGT 409 *AI Foundations for Managers*: final project. The submitted report and slides are in [`deliverables/`](deliverables/) (`report.html`, `slides.html`; self-contained, open in any browser).

> **Status: Milestone 5 (Body: progress tracking and a recovery map, on top of nutrition, training, the questionnaire and the AI Coach).**
>
> **Working now:**
> - accounts, with each user's data kept private, and a short first-run questionnaire;
> - profile and training preferences;
> - self-reported limitations;
> - the calorie and macro target calculator;
> - **nutrition logging:** offline USDA food search, barcode lookup (typed, camera or photo), recent foods, manual entries, a time-stamped food log, plausibility checks, and daily progress bars;
> - **training:** workouts generated for your goal, experience, equipment, time budget and reported limitations; review the whole routine; swap exercises from compatible alternatives; log sets, reps and weights (kg or lb); a finished-workout summary with planned vs. actual time; history;
> - health checks and the AI connection check.
>
> - **AI Coach:** a router plus a Nutrition Agent, Training Agent and Progress Coach (`gpt-6-luna`). They use read-only tools on your real records, with answer checks, run traces and token and cost tracking.
>
> - **Body:** record weight and waist, chest, hips, biceps and thigh measurements (with comparisons and a chart), plus a front/back muscle-recovery map estimated from your logged workouts, with an optional self-reported soreness rating. No AI calls.

---

## Quick start (about 5 minutes)

**You need:** Python **3.12 or newer**. Node.js is **not** needed: the built web interface is committed in `frontend/dist`.

**1. Put the key where Venn can find it.**

Venn reads `.env` from **this repository's folder first**, then from **the folder one level above it**. For example, the teaching staff's layout works as is:

```
submissions/
├── .env          <- PORTKEY_API_KEY=...   (found automatically)
└── venn/         <- this repository
```

To use your own key instead, copy the example file and fill it in:

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

Without a key, Venn still runs. AI features show as **Disabled**, and everything else works.

**2. Create a virtual environment and install** (run from the repository folder):

```bash
python -m venv .venv
```

Activate it.

- **Windows (PowerShell):**

  ```powershell
  .venv\Scripts\Activate.ps1
  ```

- **macOS / Linux:**

  ```bash
  source .venv/bin/activate
  ```

Then install the requirements:

```bash
pip install -r requirements.txt
```

**3. Start Venn:**

```bash
python run.py
```

The first start creates the SQLite database in `data/venn.db`, runs the migrations, loads the bundled food catalog (a few seconds), and adds the demo account with a week of example food entries and two completed example workouts (labelled **Demo data**).

**4. Use it.** Open **http://127.0.0.1:8000** and log in with:

| Username | Password |
|---|---|
| `demo` | `venn-demo-2026` |

You can also create your own account on the sign-in page.

- **Stop:** press `Ctrl+C`.
- **Port already in use:** `python run.py --port 8010`.

### Try the nutrition workflow

1. Open **Nutrition** in the sidebar (on a phone: the bottom bar). The demo account already has today's breakfast, lunch and a snack.
2. Press **+ Add food** (on a phone: the round **+** button at the bottom centre).
3. Pick a food in one of four ways:
   - **Recent:** foods you logged before, with the last quantity you used;
   - **Search:** for example `chicken breast`, `oats` or `banana`;
   - **Barcode:** type `888849009305` (Quest protein bar) or `044000065713` (Oreo). The full list of products in the sample is under "Products in the offline barcode sample". **Scan with camera** and **Scan from photo** decode a real barcode in the browser;
   - **Manual:** enter a food from its label.
4. Set the quantity and unit (grams, ounces, cups, servings...) and the date and time eaten, then press **Add to log**.
5. Try an implausible entry, such as `150` servings of the protein bar. Venn stops, explains the problem, and offers **Use 150 g instead**.
6. Tap any entry in the log to change its quantity, unit or time, or to delete it. Use the arrows or the date picker to see other days.

No AI model is called for search, barcode lookup, logging or any nutrition calculation.

### Try the workout lifecycle

1. Open **Training**. History shows the two demo sessions, with planned vs. actual time.
2. Leave **Workout** on "Next in my plan" (or pick a day type), set **Time available**, and press **Generate workout**.
3. Review the whole routine.
   - "Why this workout" explains the split, the time estimate, the equipment, and how your reported limitations were applied. The demo user reported the lower back as "train with caution", so heavy spinal-loading lifts are left out and moderate ones are flagged.
   - Press **Replace** on any exercise to choose from compatible alternatives.
4. Press **Start workout**. Enter the weight and reps and press **Log set** (no confirmation). A rest timer starts after each set.
5. Press **Finish workout** to see actual vs. planned minutes, sets and volume. The session then appears in History.

No AI model is called for training. The generator is deterministic and works without an API key.

### Try the Body page

1. Open **Body**. Use the **Progress / Recovery** toggle at the top right.
2. **Progress:** pick a date and enter your weight (shown in your kg/lb setting), then press **Save weight**. With two or more entries you see the difference and a chart. Add any of waist, chest, hips, biceps or thigh (cm or in, following your height setting) and compare the latest entry with an earlier one. Implausible values (e.g. 12 kg) are rejected with a message. Saving again for the same date replaces that day's entry.
3. **Recovery:** each of the ten muscle groups is coloured from your **logged** sets in completed workouts. Grey means not assessed (no logged sets in 7 days). Light, medium and dark red mean low, moderate and high estimated residual fatigue. Click a region to see the workout, exercises and sets behind it, and optionally record your own 0–10 soreness. That rating is kept separate from the estimate.

The recovery thresholds are illustrative heuristics, not medical rules: see [docs/milestone5.md](docs/milestone5.md).

### Try the AI Coach (needs PORTKEY_API_KEY)

1. Open **Coach**. Pick an example question (for example "How am I doing against my protein goal?") or type your own, then press **Ask**.
2. The answer card shows:
   - which agent answered and how it was routed;
   - the tools it used;
   - whether every number matched your records;
   - safety flags;
   - tokens and estimated cost;
   - the full run trace.
3. The **Your numbers** card is calculated by Venn without AI. It works even without a key, as does the rest of the app; the Coach then shows "unavailable".

Details: [docs/milestone4.md](docs/milestone4.md) covers the architecture, tools, safety defences, live runs, token measurements and the evidence table.

### Check the AI connection

- **Without a model call:** `GET /api/health` reports whether a key was found.
- **With a model call:** on the Dashboard, the **AI Coach → Test connection** button makes one tiny `gpt-6-luna` call. It shows the latency and the real token counts. The result is cached for 10 minutes to protect the budget.

## Reset the demo data

```bash
python scripts/seed.py --reset
```

This deletes `data/venn.db`, recreates it, reloads the food catalog, and adds the demo user with their example food entries and demo workouts again.

## Run the tests (no network, no API key needed)

```bash
cd backend
python -m pytest
```

The backend tests block every non-loopback network connection.

The frontend tests need Node.js 20 or newer:

```bash
cd frontend
npm ci
npm test
```

## Frontend development (optional, needs Node.js 20+)

```bash
cd frontend
npm ci
npm run dev          # http://127.0.0.1:5173, proxies /api to the backend on :8000
npm run build        # refreshes frontend/dist, which FastAPI serves
npm run screenshots           # with the app running: nutrition screenshots to docs/evidence (uses local Chrome/Edge)
npm run screenshots:training  # with the app running: performs a short real workout and captures the training screens
npm run screenshots:profile   # with the app running: Home, Settings (unit switches), Training, onboarding
npm run screenshots:coach     # with the app running AND an API key: asks live Coach questions (uses tokens)
npm run screenshots:body      # with the app running: Body Progress and Recovery views (read-only)
```

---

## How it is built

```
React + Vite + TypeScript (frontend/, built into frontend/dist)
        │ fetch /api/* with an HTTP-only session cookie
        ▼
FastAPI (backend/app)
  ├─ routers/       auth, profile & targets & limitations, nutrition (foods + food log), training, health
  ├─ services/      deterministic logic: targets, units & nutrition math, plausibility checks,
  │                 barcode validation, offline food search, catalog loader,
  │                 exercise catalog, workout rules (compatibility, duration), workout generator
  ├─ data/          bundled USDA food catalog and curated exercise catalog (offline; see docs/data_sources.md)
  ├─ security.py    argon2 password hashing, server-side sessions, login throttling
  ├─ ai/client.py   the only place that calls the model (Portkey → gpt-6-luna)
  └─ models.py      SQLAlchemy tables; Alembic migrations in backend/migrations
        ▼
SQLite (data/venn.db)
```

### Design rules (they apply to the AI agents in later milestones too)

- **The user's identity comes only from the login session.** No route accepts a user id. Rows looked up by id are always filtered by the session's user, so another user's id returns `404`. Tests prove this for every route.
- **Numbers come from code, not from the model.** The target calculator (`backend/app/services/targets.py`) and the nutrition math (`backend/app/services/nutrition.py`) use published formulas and data, and their tests are checked against hand calculations.
- **Logged nutrition never changes behind your back.** Each entry stores the values it was logged with. Later catalog updates do not rewrite history, and edits recompute from the stored values.
- **Safety minimums.** Venn never goes below these:
  - **Calories:** 1,200 kcal (female or unspecified) or 1,500 kcal (male), and never below the estimated resting energy.
  - **Rate of change:** at most 1% of body weight per week to lose, or 0.5% to gain.
  - **Age:** adults only (18 to 100).
  - **Manual targets:** must pass the same rules, and the macros must add up to within 10% of the calories.
- **Model:** `gpt-6-luna` only, through the course Portkey key. There is no fallback model. If the provider is unreachable, Venn reports it and keeps working.
- **Secrets:** `.env` is git-ignored, and the key is never logged or returned by any route. A test checks this.
- **Limitations are reported by the user.** Venn stores them only to filter exercises later. It does not diagnose injuries or decide what is medically safe.

### Target formulas

| Step | Formula |
|---|---|
| Resting energy (BMR) | Mifflin-St Jeor: 10·kg + 6.25·cm − 5·age + (+5 male / −161 female / −78 unspecified) |
| Maintenance (TDEE) | BMR × 1.2 / 1.375 / 1.55 / 1.725 / 1.9 (sedentary to extremely active) |
| Goal adjustment | ± rate% × body weight × 7,700 kcal/kg ÷ 7 |
| Calories | Rounded to 10 kcal, then raised to the safety minimum if needed |
| Protein | 1.6 / 2.0 / 2.2 g per kg, capped at 35% of calories |
| Fat | 30% / 40% / 20% of calories (balanced / lower-carb / lower-fat), at least 0.5 g/kg |
| Carbohydrate | The remaining calories ÷ 4 |

These are population estimates, not medical advice. The app shows this disclaimer next to every target.

### Nutrition rules

| Topic | Rule |
|---|---|
| Food data | USDA FoodData Central: 7,793 SR Legacy generic foods, plus 20 barcoded packaged products from the Branded Foods data (manufacturer labels). Values are per 100 g, or per 100 ml for liquids. Only foods with all four core values are included. |
| Units | g, kg, oz, lb (or ml, L, fl oz for liquids), USDA household measures (such as "1 cup, chopped = 140 g"), and label servings for packaged products |
| Calculation | value = value per 100 x quantity x unit size / 100, rounded to 0.1. Daily totals are sums of the stored entry values. |
| Time | Entries store the local wall-clock date and time when the food was eaten (no time-zone conversion). Days are calendar days. |
| Targets per day | A day uses the target that was in effect on that date. Days before the first target show no target. |
| Plausibility | **Rejected:** quantity of 0 or less, more than 25 kg, or more than 30,000 kcal in one entry. **Needs confirmation or a fix:** 20 or more servings, more than 3 kg or 3,000 kcal in one entry, large kg/lb/L numbers, a day above 10,000 kcal, or manual macros that don't match the calories. |
| Barcodes | UPC-A, EAN-13, EAN-8 and GTIN-14, with check-digit validation. Lookup is offline against the bundled sample only. |

### Training rules

| Topic | Rule |
|---|---|
| Exercises | 80 curated from free-exercise-db (public domain), each tagged with a movement pattern, equipment, level, reps or time, unilateral, and the body areas it loads |
| Split | Your preferred split, or ≤3 days: full body; 4 days: upper/lower; 5+ days: push/pull/legs. Day types rotate through completed sessions. |
| Equipment | Every exercise's equipment must be in your list ("body only" is always available) |
| Limitations | **Avoid:** excludes every exercise that loads the area. **Caution:** excludes heavy loading and flags moderate loading. Venn only uses limitations you report; it never infers or diagnoses anything. |
| Time | Estimate = 5 min warm-up + sets (reps x 3 s + 15 s setup; doubled per side for unilateral moves) + rest between sets + 2 min per exercise changeover (1 min if the equipment doesn't change). Over budget: drop the lowest-priority exercises, then sets. If it still won't fit, Venn explains why. |
| Replacement | User-initiated; same movement pattern first. The server re-checks equipment and limitations, and your choice is remembered for future workouts. |
| Logging | Weight entered in kg or lb (from your profile units), stored in kg. Planned and logged values are shown side by side. Actual duration = Finish - Start. |

## Repository map

| Path | Contents |
|---|---|
| `run.py` | One-command start: migrate, seed the demo user, serve the app |
| `backend/app/` | FastAPI app, models, services, routers, AI client |
| `backend/migrations/` | Alembic migrations |
| `backend/tests/` | pytest suite (offline) |
| `frontend/src/` | React app; `frontend/dist/` is the committed production build |
| `scripts/seed.py` | Create or reset the database and the demo user |
| `scripts/build_food_catalog.py` | Rebuilds the bundled food files from USDA downloads (not needed to run the app) |
| `scripts/router_experiment.py` | Keyword router vs. model router cost experiment (needs a key; writes `docs/evidence/router_experiment.json`) |
| `deliverables/` | `report.html`, `slides.html` and `build.py`, which regenerates both from `docs/evidence/` (`python deliverables/build.py`) |
| `scripts/build_exercise_catalog.py` | Rebuilds the curated exercise catalog from free-exercise-db (not needed to run the app) |
| `frontend/scripts/screenshots.mjs` | Captures evidence screenshots of the running app |
| `docs/` | Milestone notes, pricing investigation, evidence |
| `AI_prompts.md` | Major development prompts and milestones |
| `.env.example` | Placeholder for every environment variable Venn reads |

## Known limitations

See [docs/milestone1.md](docs/milestone1.md), [docs/milestone2.md](docs/milestone2.md), [docs/milestone3.md](docs/milestone3.md), [docs/milestone3_5.md](docs/milestone3_5.md), [docs/milestone3_6.md](docs/milestone3_6.md) and the protein review in [docs/protein_review.md](docs/protein_review.md) for details.

- **Protein:** 1.6 / 2.0 / 2.2 g per kg (shown per lb for imperial users) of current weight, or of target weight when deliberately losing weight with a lower target set. It is capped at 35% of calories and shown as a +/-5% daily range (a usability tolerance, not a physiological threshold). This is general guidance, not a personalised clinical recommendation.

- **Activity factor:** the calorie calculator still uses the standard activity multipliers, which conventionally include exercise, even though the question now asks about activity outside workouts. This was not recalibrated (see milestone3_5.md). Target weight and date are informational; the chosen pace sets the calories.

- **Body / recovery:** the recovery map is a simple heuristic from logged sets (primary muscle 1.0, secondary 0.5, 72-hour linear fade, fixed thresholds). It ignores load, effort, sleep and individual differences, and it does not measure soreness, injury or readiness. Logging a body weight does not change the weight used for your targets; update it in Settings.
- **AI Coach:** grounding checks values, not meaning; the injection filter is pattern-based, but permissions, user binding and read-only access are enforced in code (see milestone4.md).
- **Training:** the duration constants are reasoned defaults, not calibrated. The exercise "loads" tags are a conservative filter, not medical guidance. Progression is simple (same weight, or a small increase after hitting the top of the rep range).
- **Barcodes:** only the 20 bundled products are recognised; there is no online product database. Camera scanning uses the browser camera and is not yet verified on a physical phone. Typed lookup and decoding from a photo are verified.
- **Food data:** SR Legacy is the 2018 USDA release, and names use USDA's wording (e.g. "Chicken, broilers or fryers, breast..."). There are no saved multi-food meals yet.
- **Login throttling** is kept in memory, so it resets when the server restarts.
- **Cost figures** use the professor's class reference prices (see [docs/pricing_investigation.md](docs/pricing_investigation.md)). Token counts are measured; dollar amounts are estimates.
