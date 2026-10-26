# Milestone 1: Foundation

## Scope delivered

- **Repository and runtime:**
  - a dedicated `venn/` repository;
  - one-command start (`python run.py`);
  - the built frontend is committed, so evaluators don't need Node.js.
- **Database:**
  - SQLite through SQLAlchemy 2, with Alembic migrations (`0001_initial_schema`);
  - a test checks that the migrations match the models exactly.
- **Accounts:**
  - registration, login and logout;
  - argon2 password hashes;
  - server-side sessions, stored only as SHA-256 token hashes, in HTTP-only, SameSite=Lax cookies;
  - a login throttle (5 failures per 5 minutes per username);
  - the same error message for a wrong password and an unknown user.
- **Data isolation:**
  - every route takes the user from the session;
  - rows looked up by id are always filtered by that user;
  - request bodies reject unknown fields, so a body can't carry a `user_id`.
- **Profile and settings:**
  - body stats;
  - nutrition goal and rate, protein level, diet style, dietary preferences;
  - training goal, experience, days per week, session length, equipment (using free-exercise-db's names), preferred split;
  - units (metric or imperial, converted in the UI and always stored in metric).
- **Self-reported limitations:**
  - body area, temporary or ongoing, "avoid" or "caution", and an optional note;
  - add, update, mark resolved, and delete;
  - the app says clearly that Venn does not diagnose injuries or infer limitations.
- **Target calculator:**
  - transparent formulas, with the breakdown stored on every target version;
  - safety minimums and input validation;
  - manual override, validated by the same rules;
  - targets are versioned. Calculated targets update when the profile changes; manual targets are kept until the user switches back.
- **Health checks:**
  - `GET /api/health` reports the app, database and AI status without calling the model;
  - `POST /api/health/ai` requires login, makes one tiny `gpt-6-luna` call, records real token usage in `ai_usage`, and caches the result for 10 minutes.
- **UI:**
  - a blue-grey interface with a sidebar on desktop and a bottom bar on phones;
  - sign-in, dashboard, settings, and "coming soon" pages for the modules not built yet;
  - the Venn logo is built in CSS.

## Adjustments to the approved architecture, and why

| Change | Reason |
|---|---|
| Product renamed from FitSync to **Venn**; the name lives in `backend/app/branding.py` and `frontend/src/brand.ts` | Product decision. |
| The model is fixed to `gpt-6-luna`; there is no allow-list of other models | The course instructions say the course key may be used with `gpt-6-luna` only. |
| `.env` is looked up in exactly two places: the repo folder, then the folder above it | This is what the course's grading setup requires. The discovery report had proposed up to two parent folders. |
| `frontend/dist` is committed, and FastAPI serves it | G10: evaluators should not need Node.js. |
| Added a `training_limitation` table and settings UI in Milestone 1 | Requirement from the competitive audit. Workouts will filter exercises with it in Milestone 3. |
| Added an `ai_usage` table in Milestone 1 | G2: start recording real token counts now, as evidence for the report. |
| `run.py` runs the migrations and seeds the demo user on every start (both are idempotent) | Fewer setup steps for evaluators. |

## Unresolved dependencies and limitations

- **Pricing:** see `pricing_investigation.md`. No confirmed per-token price yet.
- **Login throttle:** kept in memory, so it resets on restart and is per process. That is acceptable for a local, single-process app.
- **Age:** worked out from the birth year only, so it can be off by up to one year.
- **Sex options:** the formula needs a sex value. "Prefer not to say" uses the midpoint of the male and female constants, which is a documented approximation.
- **Protein:** based on total body weight. For people with high body fat this can overestimate needs. The 35% cap limits the extreme cases, and lean-mass input is possible future work.
- **Safety minimums:** these are commonly cited general minimums, not clinical thresholds. The app shows a disclaimer.
- **Not verified on macOS or Linux.** It was only run on Windows 11 with Python 3.14.
- **The deadline is Monday, 2026-10-26 at 6:00 PM** (course PDF). Milestones 2 to 5 must be scoped to fit.

## Evidence

- `docs/evidence/m1_backend_tests.txt`: pytest output.
- `docs/evidence/m1_frontend_tests.txt`: Vitest output.
- `docs/evidence/m1_fresh_clone.txt`: transcript of a fresh-clone setup with timings.
- `docs/pricing_investigation.md`: the first measured model call.
