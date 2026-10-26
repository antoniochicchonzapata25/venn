# Milestone 3.6: Questionnaire, settings and protein logic

A time-boxed refinement before AI agent integration. All database changes are additive (migration `0005`: `gym_location`, `cardio_schedule`, `eating_pattern`, `eating_pattern_other`, `exercise_ability`, all nullable). Existing profiles and API payloads keep working.

## What changed

1. **Strength and cardio scheduled separately.**
   - **Strength:** "How many days a week would you like to strength train?" (1–7, strength only).
   - **Cardio:** "How would you like to schedule your cardio?" with four options: on my strength-training days, on separate days, a mix of both, or no cardio for now.
   - **Follow-ups (if cardio):** two separate questions, cardio days per week (1–7) and session length (10–60 min).
   - **Effect on workouts:** "strength days" and "mix" add a cardio block to strength workouts, within the time budget (existing rule). "Separate days" keeps strength workouts strength-only.
   - **Weekly summary:** `/api/training/options` returns a `weekly_plan` summary. No concurrent-training optimisation was added.
2. **Duration ranges.**
   - **Ranges:** 15–30, 30–45, 45–60, 60–75, 75–90, 90–105 and 105–120 minutes, plus "More than 120 minutes" with custom values of 135, 150, 165 or 180 (15-minute steps; the schema's maximum is 180).
   - **Stored value:** the **upper bound** is stored as `session_minutes`, so the deterministic generator is unchanged and never exceeds it (tested at every bound).
   - **Older values:** non-standard values (e.g. 50) display as "Up to 50 minutes".
3. **Workout location.** Exactly six options, each with a description and preset equipment: commercial gym, strength gym, local gym, home / garage gym, minimal equipment, and bodyweight / outdoors.
   - **Onboarding:** choosing a location pre-selects equipment and then shows the list for adjustment.
   - **Settings:** a "Use … equipment" button applies the preset.
   - **Source of truth:** the final equipment list (tested: location "bodyweight" with dumbbells selected keeps the dumbbells). No claims are made about real facilities.
4. **Protein review.** See `docs/protein_review.md` for the original behaviour, the sources, the decision and its limitations.
   - **Reference weight:** current weight, or target weight when deliberately losing with a lower target.
   - **Unchanged:** the multipliers and the 35% cap.
   - **Units:** shown in g/kg or g/lb, with the target unchanged by unit switching.
5. **Protein range.**
   - **Range:** ±5% of the unrounded target. Home and Nutrition show "Goal: 156–172 g · 82 g eaten, 74 g to reach your range".
   - **States:** below, within and above, with clear wording.
   - **Unchanged:** calories, carbs and fat.
6. **Eating pattern.** "Do you follow a particular eating pattern or have dietary restrictions?" Options: no specific restrictions (explicit), vegetarian, vegan, pescatarian, or other (with a text field).
   - **Requirements kept separate:** dietary requirements (dairy-free, gluten-free, nut-free, halal, kosher) stay a separate optional list in Settings.
   - **Compatibility:** `dietary_preferences` still includes the pattern for older readers.
7. **Exercise ability.**
   - **Question:** a short, skippable "How many reps can you do with good form?" for push-ups, pull-ups/chin-ups and dips (can't do one yet / 1–4 / 5–9 / 10–14 / 15+ / not sure).
   - **Storage:** saved to the profile and editable in Settings.
8. **Onboarding.**
   - **Format unchanged:** still one question per screen with a progress bar, Back/Continue and "Skip for now". Complete profiles are not sent through it again.
   - **New screens:** location (with equipment on the same screen), cardio schedule, cardio days, cardio length, and ability (one screen for all three exercises).

## Does exercise ability affect workouts?

Yes, in a small, deterministic way.

- **Generated workouts:** if the user can't do one rep yet, the matching bodyweight moves are left out (push-ups → Pushups and close-grip push-ups; pull-ups → Pullups and Chin-Up; dips → Bench Dips), so the generator picks other variations (tested).
- **Replacements:** these moves stay available but carry a note.
- **Not used:** other answers don't change reps or levels, and they are not used as an overall strength assessment.

## Tests

- **Backend: 158 passed.** That is all 127 previous tests plus 31 new ones in `tests/test_questionnaire.py`:
  - protein reference weight (default, losing with target, fallbacks, cap);
  - range calculation and boundary rounding (170.4 → below, 170.5 → within, 189.4 → within, 189.5 → above);
  - the no-target case, and the day summary's range;
  - unit independence of the target;
  - separate cardio and strength frequency, and cardio schedule rules;
  - eating pattern, including the "other" text;
  - location not restricting equipment;
  - ability saving and validation;
  - "can't do one yet" excluding moves from generation;
  - workouts never exceeding 30–180 minutes.
- **Frontend: 50 passed.** That is the 43 previous tests plus 7 new in `src/test/questionnaire.test.tsx`: range messages and display, the no-target fallback, reference weight, g/kg vs. g/lb, duration labels, and location presets.
- **Updated tests:**
  - **Onboarding test:** now walks the new questions (strength days, duration range, location preset and customisation, cardio schedule, days and length, ability, g/lb protein, "Other" eating pattern).
  - **Settings unit test:** now uses the duration and days dropdowns.
  - **Mock backend:** offers bands and kettlebells so presets can be customised.

  No assertions were removed.

Evidence: `docs/evidence/m36_backend_tests.txt` and `docs/evidence/m36_frontend_tests.txt`. Screenshots: `docs/evidence/m35_home.png` (protein range), `m35_settings.png` (new settings fields), and `m35_onboarding_goal.png`.

## Known limitations and migration risks

- **Older profiles** have the new fields empty: Settings shows "Not answered", and nothing is required. Cardio for older profiles is inferred from `cardio_in_plan` for display. Eating pattern is inferred from `dietary_preferences` when it contains vegetarian, vegan or pescatarian.
- **Protein may change on save:** saving a profile recalculates calculated targets. A user who is losing weight and has a target weight will see protein change (for example 220 → 180 g for 110 → 90 kg). Manual targets are not affected.
- **Cardio on separate days** is recorded but not scheduled into specific days; there is no weekly calendar.
- **Custom durations** stop at 180 minutes (existing schema limit).
- **Ability answers** only remove moves the user can't yet do; they don't choose assisted variations or change reps.
- **Not re-captured:** the onboarding location and ability screens.
