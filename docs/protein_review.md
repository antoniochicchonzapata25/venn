# Protein target review (Milestone 3.6)

## Original behaviour (before this milestone)

Inspected in `backend/app/services/targets.py`:

| Question | Answer |
|---|---|
| Which weight was used? | **Current body weight** (`profile.weight_kg`) for every user. |
| Preference → multiplier | Flexible = 1.6, Balanced = 2.0, High protein = 2.2 g per kg (`PROTEIN_G_PER_KG`). |
| Target or reference weight? | Not used. Target weight didn't exist before Milestone 3.5; after that it was stored but ignored for protein. |
| Response to goal changes | Only indirect: the goal changes calories, and protein is capped at 35% of calories, so a large deficit could lower the protein target. |
| Response to weight changes | Linear: each kg of current weight added 1.6–2.2 g. |
| Response to units | None. Weight is stored in kg, so kg/lb display never changed the target. |
| Calorie cap | If protein × 4 kcal is more than 35% of calories, protein is set to 35% × calories ÷ 4. Carbs fill the remaining calories. |

## Sources consulted

- **Jäger R. et al. (2017)**, *International Society of Sports Nutrition position stand: protein and exercise*, J Int Soc Sports Nutr 14:20. Recommends **1.4–2.0 g/kg/day** for most exercising people, and notes that higher intakes (about 2.3–3.1 g/kg of fat-free mass) may help resistance-trained people keep lean mass during calorie restriction.
- **Morton R.W. et al. (2018)**, *A systematic review, meta-analysis and meta-regression of the effect of protein supplementation on resistance training-induced gains in muscle mass and strength*, Br J Sports Med 52:376–384. Gains in fat-free mass levelled off at about **1.6 g/kg/day**, with an upper 95% confidence limit of about **2.2 g/kg/day**.
- **Helms E.R. et al. (2014)**, *A systematic review of dietary protein during caloric restriction in resistance trained lean athletes*, IJSNEM 24(2):127–138. Suggests 2.3–3.1 g/kg of **fat-free mass** for lean athletes in a deficit. This supports scaling protein to lean tissue rather than total mass, but Venn has no reliable fat-free-mass measure.
- **Clinical guidance for people with obesity** (critical-care and dietetic practice) commonly bases protein on an adjusted or ideal reference weight rather than actual body weight, to avoid over-estimating needs. It was not reviewed in depth for this time-boxed milestone. It is noted here as the direction the evidence points, not as a source Venn implements.

## Decision (what Venn does now)

1. **Multipliers unchanged.** 1.6, 2.0 and 2.2 g/kg sit inside, or at the edge of, the ranges above (1.6 = where gains plateau on average; 2.0 = top of the ISSN range; 2.2 = upper confidence limit in Morton 2018). They are **general guidance for active adults**, not a personalised clinical recommendation.
2. **Reference weight.**
   - **Current weight** by default.
   - **Target weight** when the user is deliberately losing scale weight **and** has set a lower target weight. This avoids scaling protein to weight the user plans to lose, which is a conservative, practical stand-in for the "reference or adjusted weight" approach.
   - **When it applies:** only when the user chooses it by entering a target. Venn never assumes that a higher body weight means excess fat.
3. **Not used:** BMI, self-reported body-fat % and lean-body-mass estimates. Self-reported body fat isn't reliable enough to drive a calculation, and BMI can't tell muscle from fat.
4. **Cap kept.** The 35%-of-calories cap and all existing calorie safety floors are unchanged.
5. **Units.** The stored multiplier is always g/kg. Imperial users see the equivalent in g/lb (1.6 → 0.73, 2.0 → 0.91, 2.2 → 1.00 g/lb), so switching units never changes the target (tested).
6. **Transparency.** Each formula target stores `protein_reference` ("current weight" / "target weight"), `protein_reference_kg`, `protein_g_per_kg` and the unrounded value (`protein_unrounded`) in its breakdown.

## Daily range instead of a single pass/fail number

- **Range:** the nominal target **±5%**, calculated from the **unrounded** target and rounded half-up to whole grams. Example: nominal 180 g → **171–189 g**.
- **Status:** whole grams eaten (rounded half-up) are compared with the whole-gram range:
  - **below** shows how many grams are needed to reach the lower bound;
  - **within** says the goal has been met;
  - **above** shows grams above the upper bound, adding "More protein isn't necessarily better".
- **Missing data:** with no target there is no range, and the bar falls back to "No target set". An empty log reads "Nothing logged yet; N g to reach your range".
- **Why ±5%:** a **usability tolerance**, not a physiological threshold. At typical targets (100–200 g) it is about ±5–10 g, roughly one portion of a high-protein food. That makes small daily differences read as success instead of failure while staying close to the nominal value. No source defines a "correct" tolerance.
- **Manual targets:** the range is based on the protein grams the user entered.
- **Unchanged:** calories, carbs and fat still show a single target and remaining amount.

## Still needs validation

- **Target weight as the reference** is a product decision based on common practice; a registered dietitian should review it. People who are losing weight but haven't set a target still get protein based on current weight.
- **Lean athletes in a deficit** may be better served by fat-free-mass-based targets (Helms 2014). Venn can't support that without a reliable body-composition measure.
- **The ±5% tolerance** hasn't been tested with users.
