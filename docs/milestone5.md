# Milestone 5: Body (Progress and Recovery)

The **Body** page replaces the earlier "coming soon" placeholder. A segmented **Progress / Recovery** toggle switches between the two views; the selected view is kept in the URL (`/body?view=recovery`). Nothing on this page calls a model.

## Progress

| Feature | Behaviour |
|---|---|
| Weight | One entry per date. It is stored in kg and entered and shown in the user's kg/lb setting. The page shows the latest entry, the previous one, the difference (and days between) and an SVG line chart when there are two or more entries. History has a delete button per entry. |
| Measurements | Waist, chest, hips, biceps and thigh, stored in cm and entered in cm or in (following the height setting). Any field can be left blank. The comparison table shows each field's latest value against the previous entry that recorded the *same* field, or against any earlier entry the user picks. Missing values show as "not recorded". |
| Same date | Saving again for a date replaces that date's entry, and the UI says so. |
| Validation | Weight must be 25–350 kg (55–772 lb). Each measurement has its own plausible cm range: waist 40–250, chest and hips 50–250, biceps 15–80, thigh 25–120. Dates must be from 2000-01-01 to tomorrow (UTC), which allows for time zones. Unknown fields such as `user_id` are rejected. Error messages are given in the unit the user used. |
| Honesty | No body-fat estimate. Notes say weight changes can reflect water and timing, not only fat or muscle. Logging a weight does **not** change the weight used for targets; that stays a deliberate Settings change. |

## Recovery estimate (`backend/app/services/recovery.py`)

This is a deterministic, illustrative heuristic. It is **not** a validated recovery model.

1. **Mapping.** Each exercise uses its free-exercise-db `primary_muscles` and `secondary_muscles` from the bundled catalog.
   - **Weights:** primary counts 1.0 per set and secondary 0.5.
   - **Groups:** lats, middle back and traps map to **Back**; lower back to **Lower back**; abdominals to **Abs**; the other muscles map one-to-one.
   - **No double counting:** if several catalog muscles of one exercise map to the same group, the group takes the highest weight, so the exercise counts once.
   - **Ignored:** calves, forearms and "cardiovascular system" are not among the ten groups.
   - **Tested:** every catalog muscle is mapped or explicitly ignored.
2. **What counts.** Only sets actually logged (reps > 0 or a duration) in **completed** workouts count. Planned or in-progress workouts don't count, nor do exercises with no logged sets.
3. **Residual load** = Σ over completed workouts in the last 7 days of weighted sets × max(0, 1 − hours since finished / 72).
4. **Categories.**

   | State | Condition | Colour |
   |---|---|---|
   | Not assessed | No weighted sets for the group in 7 days | Grey, dashed outline |
   | Low | Residual < 2 | Light red |
   | Moderate | Residual 2 to < 5 | Medium red |
   | High | Residual ≥ 5 | Dark red |

   Example: 6 primary sets just finished counts as high; 36 h later it is 3.0 (moderate); 60 h later 1.0 (low).
5. **Side indicators.**
   - **Last workout:** days since the last completed workout (calendar days in the browser's time zone), its date, and the number of the ten groups it trained with logged sets.
   - **Counts:** low, moderate, high and not assessed, which always add up to 10.
6. **Detail panel.** Shows the group's latest workout (labelled if it is demo data), each exercise with its logged sets and whether the muscle is primary or secondary, weighted sets over 7 days, the residual against the thresholds, and how the estimate is calculated.

**No history:** every group is "not assessed", and the page says that there is nothing to estimate yet. No values are invented.

**Disclaimer (shown in the UI):** "An estimate from your logged workouts using illustrative thresholds, not a medically validated recovery rule. Real recovery varies between people (sleep, nutrition, stress, training age). It does not measure soreness or injury or tell you whether it is safe to train."

## User-reported soreness (optional, implemented)

- **Rating:** a 0–10 rating per muscle group (`PUT/DELETE /api/body/soreness/{group}`), shown as **user-reported** with the time it was recorded.
- **One per group:** a new rating replaces the previous one.
- **Separate:** it is stored apart from the estimate and never changes it (tested).

## AI Coach

`get_progress_metrics` (Progress Coach) now includes a read-only `body` summary:
- the number of weight entries;
- latest and previous weight, and the change;
- the measurements recorded, with the latest value and change for each.

It reads the session user's records only (tested with two users). The Progress Coach instructions add: report body values as recorded, and never attribute a change to fat loss or muscle gain. No new tool and no extra model calls were added. The live runs in milestone4.md predate this change and were not re-measured.

## API

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/api/body/weights` | POST `{entry_date, weight, unit: kg\|lb}` |
| DELETE | `/api/body/weights/{id}` | 404 for other users' rows |
| GET/POST | `/api/body/measurements` | POST `{entry_date, unit: cm\|in, waist?, chest?, hips?, biceps?, thigh?}` |
| DELETE | `/api/body/measurements/{id}` | 404 for other users' rows |
| GET | `/api/body/recovery?tz_offset=` | Estimate, counts, model description and soreness ratings |
| PUT/DELETE | `/api/body/soreness/{group}` | `{rating: 0-10}` |

Migration `0007_body_tracking` adds `body_weight`, `body_measurement` and `soreness_rating`. Each table has a unique key on user + date (or user + group) and cascades on user deletion.

## Tests

- **Backend: `tests/test_body.py`, 39 tests.**
  - empty states;
  - create, compare, replace and delete;
  - out-of-order dates;
  - validation, including unit-specific messages, future and old dates, and extra fields;
  - per-field measurement comparison with missing values;
  - cross-user denial;
  - mapping weights, and full catalog coverage;
  - classification boundaries, decay and the 7-day window;
  - secondary-muscle weighting, and unlogged sets ignored;
  - accumulation across workouts, and counts adding up;
  - local-day calculation;
  - an API run on a real finished workout;
  - in-progress workouts ignored;
  - soreness set, update, delete and validation, kept separate from the estimate.
- **Backend: `tests/test_coach.py`, 1 new test.** Body data reaches the Progress Coach tool for the right user only.
- **Frontend: `src/test/Body.test.tsx`, 6 tests.**
  - empty states, the implausible-weight error, and the latest/previous difference and chart;
  - lb units sent and shown;
  - the toggle, indicators and counts, with ten labelled regions;
  - the detail panel, soreness kept separate, and keyboard selection;
  - the no-history state;
  - the comparison logic.

Screenshots: `docs/evidence/m5_body_progress.png`, `m5_body_recovery.png`, `m5_body_recovery_mobile.png` (`npm run screenshots:body`). The weight and measurement values in the Progress screenshot are test entries typed into the demo account, not real measurements.

## Limitations

- **Simple model:** the recovery model ignores load, reps in reserve, sleep and individual differences, and its thresholds are not validated.
- **Coarse groups:** the muscle mapping is coarse. For example, "shoulders" covers front and rear delts, and "back" covers lats and traps.
- **Body tracking is basic:** one entry per date, no trend smoothing, no progress photos.
- **Demo data:** demo workouts count toward the estimate. They are labelled "Demo data" in the detail panel.
