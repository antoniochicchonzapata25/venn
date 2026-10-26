# Milestone 3.5: Profile, units, onboarding and design refresh

A time-boxed refinement before the AI agent milestone. Every change is additive: migration `0004` adds nullable or defaulted profile columns, and older API payloads still work (tested).

## Completed

1. **Unit switches beside each field.**
   - **Fields:** height (cm or ft + in), weight (kg or lb) and target weight (kg or lb). The old global metric/imperial selector is gone from Settings.
   - **Storage:** values are always stored in cm and kg. Forms keep the metric value at full precision and only convert what is shown, so switching back and forth never drifts (tested 100 round trips).
   - **Preferences:** `height_unit` and `weight_unit` are saved. The legacy `units` field mirrors the weight unit for compatibility. Training logs use `weight_unit`.
   - **Calculations** never depend on display units: identical targets in kg and lb (tested).
2. **Profile wording.**
   - **Onboarding** asks plain questions ("How many days a week would you like to strength train?", "How active are you outside your planned workouts?", "How would you describe your training experience?", "How much time do you usually have per workout?", "What level of protein intake feels realistic for you?"). Answers are selectable cards with short descriptions.
   - **Settings** uses short labels: Goal, Pace, Daily activity, Experience, Training split, Training days / week, Duration, Protein, Eating pattern, Carb / fat balance, Equipment.
3. **Goals and protein.**
   - **Goals:** "Lose body fat", "Maintain weight", "Gain muscle and strength", each with an optional clarification:
     - lose fat: also lose scale weight, or keep weight about the same (recomposition);
     - gain muscle: accept some weight gain, or keep weight changes minimal.
   - **Pace:** Gradual, Moderate or Faster replaces the %-per-week input. Each maps to the existing, tested rates (lose 0.25/0.5/0.75%, gain 0.1/0.25/0.5% of body weight per week), all within the existing safety limits.
   - **Target weight and date** are optional and only offered with a scale-weight goal. They are informational: Venn shows how long the chosen pace would take, and whether the date would need more than the maximum safe pace. **The calorie formula is unchanged:** no new or unvalidated calorie algorithm was added.
   - **Protein:** Flexible, Balanced and High protein replace the old technical labels. They map to the existing fixed values of 1.6, 2.0 and 2.2 g per kg, and the app shows the resulting grams per day.
     - **Basis:** these values sit in ranges commonly cited for active adults (for example Morton et al. 2018, *Br J Sports Med*, and the ISSN 2017 position stand).
     - **Caveats:** the app labels them general guidance, not medical advice, and keeps the existing 35%-of-calories cap.
4. **Eating pattern and body fat.**
   - **Eating pattern:** "Diet style" now means eating patterns only (vegetarian, vegan, pescatarian, dairy-free, and so on; empty = eats everything).
   - **Carb / fat balance:** the old macro split is now this separate setting. Every option explains its fat percentage, and no percentages appear as diet labels.
   - **Body fat %:** optional, explained, and stated as not used in calculations yet.
5. **Training goals and cardio.**
   - **Goals:** one primary and one optional secondary goal. New goals: muscular endurance and cardio fitness (with their own sets, reps and rest).
   - **Cardio questions:** sessions per week, typical duration, and whether to include it in the plan.
   - **Cardio in plan:** a cardio block is added at the end of each workout. It only appears if at least 28 minutes remain for strength work and the block can be 10 minutes or more, and it stays within the time budget (tested).
   - **Separate counts:** strength training days are counted separately from cardio.
   - **Training page:** the next workout is now **generated automatically** when nothing is planned. A **Training split** selector there changes the split, saved as your default.
   - **Unchanged:** all generator safety rules (equipment, limitations, budget validation).
6. **Onboarding.**
   - **Format:** one question per screen, with a progress bar, Back and Continue, selectable answers, and a "Skip for now" link.
   - **When it shows:** a logged-in user with an incomplete profile is sent there once. Existing complete profiles are never asked again.
   - **Saving:** answers save to the existing profile at the end, and everything can be edited in Settings.
7. **Visual design.**
   - **Base:** monochrome, with white surfaces, black text and selected states, and grey borders and secondary text.
   - **Navigation:** new inline-SVG icons (Home house, Nutrition chef's hat, Training dumbbell, Body stretching figure, Coach speech bubble with spark, Settings gear). They are outlined in grey when inactive and solid black when active. "Dashboard" is now **Home**.
   - **Nutrition colours:** calories blue, protein green, carbs purple, fat amber. Labels and numbers are always shown, so meaning never depends on colour.

## Tests

- **Backend: 127 passed.** That is all 119 previous tests plus 8 new in `tests/test_profile_goals.py`:
  - old payload compatibility, and units being display-only;
  - target-weight direction and date rules, and the projection maths;
  - optional-field validation;
  - new training goals, cardio fitting the budget, and the split change through Training.
- **Frontend: 43 passed.** That is the 37 previous tests (four updated for the new UI) plus new ones in `src/test/units.test.tsx`:
  - height and weight conversions with no drift;
  - goal mapping and pace limits;
  - protein grams;
  - a full onboarding run that saves the profile.

  Updated older tests:
  - **Unit switching:** now covers the unit switches and back-and-forth switching instead of the removed global selector.
  - **New users:** now covers the redirect to onboarding and the "Skip" link.
  - **Training mock:** given the new `splits` options.
  - **Navigation label:** "Dashboard" is now "Home".

Evidence: `docs/evidence/m35_backend_tests.txt` and `docs/evidence/m35_frontend_tests.txt`.

## Screenshots

`cd frontend && npm run screenshots:profile` recreates these.

| File | Shows |
|---|---|
| `docs/evidence/m35_home.png` | Monochrome Home with coloured nutrition bars and the new nav icons |
| `docs/evidence/m35_settings.png` | Settings with the ft/in and lb switches, goal clarification, pace, optional target weight/date, protein in g/day, eating pattern vs. carb/fat balance, primary/secondary goals, cardio |
| `docs/evidence/m35_training_home.png` | Training with the auto-generated next workout ready and the split selector |
| `docs/evidence/m35_onboarding_goal.png`, `m35_onboarding_scale.png` | First-run questionnaire (question 1 of 14, then the clarification) |
| `docs/evidence/m35_nutrition_mobile.png` | Phone layout in the new style |

The earlier `m2_*` and `m3_*` screenshots show the previous blue-grey styling. The features are the same.

## Known limitations

- **Activity factor:** the calculator still uses the standard Mifflin-St Jeor activity multipliers. These conventionally include exercise, while the question now asks about activity *outside* workouts. A properly separated model would need recalibrating, so it was deliberately not changed under time pressure; current targets may be somewhat conservative for people who train a lot.
- **Target weight and date** don't set calories; they only project and flag. The pace still drives the deficit or surplus.
- **Secondary training goal** is stored and mentioned in the workout explanation, but it doesn't change sets, reps or rest yet.
- **Cardio block** is generic (any modality the user chooses). Cardio sessions on days without strength training are not scheduled.
- **Onboarding** doesn't ask about limitations; it points to Settings for those.
- **Body fat %** is stored but not used (no lean-mass-based formula).
