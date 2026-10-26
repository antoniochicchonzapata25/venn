# Milestone 3: Training Core

## Delivered: the workout lifecycle

**Open Training → generate a workout → review it → swap an exercise (optional) → start → log sets → finish → see the summary and history.**

| Step | Implementation |
|---|---|
| **Exercise catalog** | 80 exercises curated from **free-exercise-db** (public domain), built by `scripts/build_exercise_catalog.py` into `backend/app/data/exercises.json`. Each has: <ul><li>name, equipment, level, muscles and short instructions from the source;</li><li>Venn's own tags: movement pattern (16 patterns), extra equipment the source omits (bench, pull-up bar), reps or time, unilateral, and **body areas it loads** (1 = moderately, 2 = heavily).</li></ul> |
| **Generation** (`services/workout_generator.py`) | Deterministic (`deterministic-v1`); needs no AI key. <ul><li>**Split:** the user's preference, or chosen from days per week (≤3 full body, 4 upper/lower, 5+ push/pull/legs).</li><li>**Day:** the requested one, or the next in rotation based on completed sessions.</li><li>**Slots:** each template slot gets the best compatible exercise. Exercises the user swapped in before rank higher; ones they swapped out rank lower.</li><li>**Prescription:** sets, reps and rest by goal (strength, muscle, general fitness, fat loss) and experience.</li><li>**Weights:** suggestions follow simple double progression from the user's last logged sets.</li></ul> |
| **Time budget** (`services/workout_rules.py`) | **Estimate** = 5 min warm-up + per set (reps × 3 s + 15 s setup, doubled for unilateral moves) + rest between sets + a 120 s changeover per exercise (60 s if the equipment doesn't change). Accessories that share equipment are grouped together. **Over budget:** drop the lowest-priority slots, then trim sets (never below 2). If even that won't fit, explain why and suggest a workable time. The plan is never shown over budget. |
| **Safety rules** (enforced in the backend before anything is shown or saved) | <ul><li>**Equipment:** every exercise's equipment must be in the user's list.</li><li>**Avoid limitation:** excludes every exercise that loads that area.</li><li>**Caution limitation:** excludes heavy loading of the area and flags moderate loading on the exercise card.</li><li>**"Other" limitations** can't be matched to exercises, and the explanation says so.</li><li>**Experience:** generated exercises stay at or below the user's level.</li><li>`validate_plan` re-checks every generated plan. Every replacement is re-checked on the server, so a client cannot insert an incompatible exercise.</li><li>Venn never infers a limitation or diagnoses anything. The explanation always ends with "general fitness guidance, not medical advice".</li></ul> |
| **Review** | The whole routine is shown at once: name, objective, estimated duration against the budget, exercises in order with sets × reps (or seconds), rest, short instructions, suggested weight with the last result, flags, and a "Why this workout" explanation. No per-exercise approval. |
| **Replacement** | User-initiated. **Replace** lists up to 6 server-filtered alternatives: the same pattern first, then the slot's other patterns. Each shows a reason, equipment, level and any flags. The user chooses one; nothing is swapped silently. Swaps are stored (`replaced_exercise_id`) and shape future generations. |
| **Logging** | **Start** stamps the start time (server time, UTC). <ul><li>Each set is weight + reps (or seconds), with **no confirmation**. Fields are pre-filled from the last set or the suggestion.</li><li>A rest timer starts after each set.</li><li>An exercise auto-completes when its planned sets are logged, and can also be marked done.</li><li>Sets can be removed.</li><li>Weights are entered in kg or lb (from the profile's units), stored in kg, and shown in both.</li></ul> |
| **Finish and summary** | Stamps the finish time and computes the actual duration. The summary shows actual vs. planned minutes and the difference ("13 min over plan"), sets logged vs. planned, volume, and new personal bests (heaviest weight vs. earlier completed sessions). Each set row shows planned and logged values side by side. |
| **History** | Completed sessions with planned vs. actual time, plus the average difference over the last 5 sessions (groundwork for future time-budget adaptation). The dashboard's "workouts done" stat now uses real data. |
| **Demo data** | The demo user gets two completed sessions, built by the real generator. They are stored with `is_demo = true` and shown with a **Demo data** badge. Their durations (88 and 71 min) are illustrative, not measured. |

## Architecture notes

- **No model calls in Training.** The prompt allowed `gpt-6-luna` "if AI is needed". The deterministic generator already meets every requirement and costs $0, so a model adds nothing yet. The upcoming Training Agent can rank or explain alternatives, but it must call the same `validate_plan` and `check_exercise` before any result is shown.
- **Equipment vocabulary.** "bench" and "pull-up bar" were added, because many exercises need them. Users without them get floor and machine variants. The demo profile includes both.
- **Time zones.**
  - **Fixed:** the nutrition day view used to compare a UTC target timestamp against a local day boundary, so after about 8 PM in New York today's target disappeared. The browser now sends `tz_offset`, and the server falls back to its own local zone. A regression test covers this.
  - **Training timestamps:** stored in UTC and shown in the browser's local time.
- **Migration 0003** adds `workout`, `workout_exercise` and `workout_set`. All rows carry `user_id`, and every query filters by the session user.

## Tests

- **Backend: 119 passed** (89 from Milestones 1–2, the new time-zone regression test, and 29 training tests). See `docs/evidence/m3_backend_tests.txt`.
- **Frontend: 37 passed** (28 earlier and 9 new). See `docs/evidence/m3_frontend_tests.txt`.

New coverage:

- **Generation:**
  - complete routine within budget, validated;
  - split by days per week, and day rotation;
  - equipment restrictions, including the bench requirement;
  - body-weight-only plans;
  - "avoid" excludes all loading, "caution" excludes heavy and flags moderate, and "other" is disclosed;
  - experience level;
  - the validator blocks bad plans.
- **Duration:** checked against hand calculations (bilateral, unilateral, same-equipment changeover); budget respected at 20–90 min; an impossible budget explains and suggests an alternative; no compatible exercises explains and suggests alternatives.
- **API:**
  - a complete profile is required;
  - the AI-disabled fallback uses `deterministic-v1` with no key;
  - regenerating discards the earlier plan;
  - unfixable constraints return HTTP 422 with alternatives.
- **Replacement:** alternatives exclude heavy lower-back loads; the server refuses an incompatible pick; the swap is remembered next time.
- **Logging:** start → log sets → finish, with an actual duration of 70 min, the difference, sets and volume; logging after completion is refused; lb entries are stored in kg; set validation (negative, too heavy, missing reps, wrong exercise, finishing with nothing logged, edit and delete).
- **Progression:** suggestions come from history.
- **Isolation:** another user's workout, alternatives, replace, discard, start, sets and finish all return 404, and their lists are empty.
- **Persistence:** history survives a restart.
- **Demo data:** demo sessions are flagged.
- **Frontend:** display logic (targets, rest, difference text, kg/lb, clock, set prefill), the full UI lifecycle with lb logging, demo history badge, and the generation-failure message.

## Evidence (real app, demo user)

`frontend/scripts/screenshots_training.mjs` recreates these. It performs a real short session.

| File | What it shows |
|---|---|
| `docs/evidence/m3_training_dashboard.png` | Training home: generator (next day, time available), history with planned vs. actual and **Demo data** badges, average difference, workouts in the last 7 days |
| `docs/evidence/m3_generated_workout.png` | A full generated Upper Body routine (full-page): the "Why this workout" explanation (split, 64 of 75 min estimate, equipment, the lower-back caution rule, disclaimer); every exercise with plan, rest, minutes, suggested weight, last result, flags and instructions |
| `docs/evidence/m3_replace_exercise.png` | Replacing Seated Cable Rows: compatible alternatives with reasons, equipment and level. Bent-over barbell rows are absent because they load the lower back heavily. |
| `docs/evidence/m3_active_logging.png` | Active session: elapsed timer vs. plan, rest countdown, logged sets (planned vs. logged), pre-filled next-set form |
| `docs/evidence/m3_active_logging_mobile.png` | The same on a phone |
| `docs/evidence/m3_workout_summary.png` | Summary of the real session the script ran. It finished seconds after starting, so the actual time is about 0 min (shown honestly), with planned time, difference, sets and volume. |
| `docs/evidence/m3_demo_history_summary.png` | A demo session summary (labelled **Demo data**): 71 min actual vs. 58 planned, +13 min, 21/21 sets |
| `docs/evidence/m3_fresh_clone.txt` | Fresh-clone rehearsal including an API-only workout lifecycle |

## Limitations

- **Duration model:** the constants (3 s per rep, 15 s setup, 120/60 s changeovers) are reasoned defaults, not calibrated. Planned-vs-actual data is now being collected so they can be tuned or personalised later; no adaptation is implemented.
- **"Loads" tags** are Venn's general descriptions of 80 exercises. They are a conservative filter, not medical guidance, and they don't cover every limitation (for example "upper back" has no tagged exercises; "other" can't be matched).
- **Progression:** suggestions are simple (same weight, or +2.5/+5 kg after all sets hit the top of the range). There is no deload or RIR tracking.
- **Not built yet:** no rest-timer sound or notifications; no editing of a completed session; no supersets or cardio.
- **Server-time timestamps:** start and finish times come from the server clock. On a hosted server in another time zone the display is still correct, because the browser converts from UTC.
