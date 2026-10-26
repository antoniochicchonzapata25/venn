# AI prompts and milestones: Venn

This log records the major development prompts given to the AI coding assistant (Claude Code), and what each one produced.

**How we worked:**
- **The student, with ChatGPT,** set product strategy, architecture decisions, specifications and quality control.
- **Claude Code** did the technical discovery, implementation, testing and reporting.

---

## Prompt 1: Technical discovery (2026-10-24)

> We are beginning development of FitSync, a final project for MGT 409: AI Foundations for Managers.
> Project objective: Build a comprehensive fitness and nutrition web application that integrates nutrition tracking, workout planning, body measurements, and AI-powered progress insights. The product is inspired by MacroFactor and Fitbod, but our goal is to create an integrated experience that is convenient, personalized, and useful. The application should be a real, functional product rather than a static prototype.
>
> Collaboration model: ChatGPT and I are responsible for product strategy, architecture decisions, feature specifications, and quality control. You are responsible for technical discovery, implementation planning, coding, testing, debugging, and reporting implementation results. For this first task, do not begin implementing the application. Focus on technical discovery and planning.
>
> Core product modules: 1. Dashboard (daily calorie and macronutrient summaries, upcoming or planned workouts, progress indicators, weekly consistency metrics). 2. Nutrition (food search, meal logging and serving-size adjustments, calorie/protein/carbohydrate/fat tracking, saved foods and meals). 3. Training (personalized workout generation; exercise selection based on goals, experience, available equipment, and available time; exercise substitutions; workout logging including sets, repetitions, and weights; historical performance tracking). 4. Body tracking (weight and body-fat percentage logging, historical charts and trends). 5. AI Coach (a Nutrition Agent, a Training Agent, a Progress Coach that uses nutrition, workout, and measurement history to generate grounded insights). 6. Profile and settings (fitness goals, training experience, equipment availability, preferences and user-defined nutritional targets).
>
> Academic requirements: The final application must support a project report explaining motivation and differentiation from existing products; agent architecture, responsibilities, tools, and model choices; a traced example of an actual agent run; measured token usage and cost per run; cost projections for 100 and 10,000 users; cost-optimization experiments and their effects on performance; safety risks and at least one demonstrably effective defense; measurable impact and honest limitations. The repository must contain a README with reproducible setup instructions and an .env.example file with placeholder values only. The teaching staff must be able to run the application from a fresh clone in no more than 10 minutes by following the README, or use a stable hosted application. The report and slide deck will be submitted as self-contained HTML files.
>
> Your tasks: 1. Inspect the existing working directory, available project files, and any relevant previous implementation that we could reuse. 2. Identify existing frameworks, dependencies, conventions, and infrastructure. Do not assume that we must start from scratch. 3. Identify the available AI model configuration and any constraints associated with the course-provided API key. 4. Recommend a technical architecture for the application (frontend, backend, database and persistence, nutrition data source, exercise dataset, AI agent orchestration, tool interfaces and permissions, testing strategy, deployment and local execution). 5. Recommend a practical multi-agent design that separates AI reasoning from deterministic calculations, data validation, and authorization. 6. Identify the main technical risks, particularly API availability, food-data quality, persistence, model cost, prompt injection, unauthorized data access, and reproducibility. 7. Propose a phased implementation plan with dependencies and acceptance criteria. 8. Recommend an initial feature scope that is ambitious enough for a strong final project but feasible to implement and test.
>
> Constraints: Do not implement features yet. Do not invent API keys, credentials, model availability, or infrastructure. Do not commit secrets or request that I paste secrets into source files. Do not rely on proprietary code or unauthorized access to MacroFactor or Fitbod. Prefer simple, maintainable architecture over unnecessary complexity. Distinguish verified facts from assumptions and recommendations. Flag any decisions that require my approval before implementation.
>
> Expected response: A structured technical discovery report containing: A. Existing environment and reusable components. B. Recommended architecture and rationale. C. Proposed database entities and relationships. D. Agent responsibilities, tools, and orchestration. E. Recommended implementation phases. F. Main risks and mitigations. G. Decisions requiring approval. H. The first implementation milestone and its acceptance criteria. Do not write application code until I review the report and approve the architecture.

**Result:** a discovery report (kept outside this repository, in `Final Project/FitSync_Discovery_Report.md`).

- **Reuse:** it found the HW5 stack to reuse (FastAPI, PydanticAI, React, Vite, TypeScript, pytest, Vitest).
- **Models:** it verified by live calls that `gpt-5.6-luna`, `gpt-6-luna` and `gpt-6-astra` all answer through Portkey, and that `response.usage` reports token counts.
- **Data:** it verified that the USDA FoodData Central download and free-exercise-db (876 exercises, public domain) are reachable.
- **Plan:** it proposed the agent design, the phases and the risks, and listed ten decisions (G1 to G10) for approval.

## Prompt 2: Milestone 1, Foundation (2026-10-25)

> We have reviewed your technical discovery report and completed a competitive audit of MacroFactor Nutrition, Fitbod, and MacroFactor Workout. We approve the recommended technical architecture, subject to the decisions and product requirements below.
>
> 1. Product direction and name. The official product name is Venn. Venn is a comprehensive fitness and nutrition platform integrating nutrition tracking, personalized workout generation and logging, body measurements, and AI-powered progress insights. The primary differentiator is an adaptive fitness experience that accounts for users' actual behavior and constraints, rather than merely generating generic recommendations. Use Venn consistently in the application, documentation, and user-facing materials. Keep the name centralized where practical to make future changes easy.
>
> 2. Competitive audit findings. Use the attached Fitness App Competitive Audit as product research. Nutrition: the food-logging experience must be fast, clear, and flexible; support different serving units and quantities; make frequently consumed foods and meals convenient to reuse; detect implausible quantities or nutritional totals before saving entries; keep the dashboard focused on the most useful information. Training: personalize routines using goals, experience, equipment, preferences, and available time; allow users to replace exercises and remember their preferences; make workout logging convenient; track sets, repetitions, weights, duration, and relevant personal records; compare planned and actual workout duration; avoid routines that consistently exceed the user's available time; account for equipment availability and exercise transitions when practical. Injury and limitations support: allow users to report exercise restrictions or temporary limitations; use explicit restrictions to exclude or flag potentially conflicting exercises; do not diagnose injuries or claim to determine medical safety; do not infer an injury or limitation that the user has not reported. Integrated insights: connect nutrition, training, and body-measurement data; generate evidence-based progress summaries; distinguish observed correlations from causal conclusions; suggest practical next steps based on recorded data. The competitive audit reflects personal observations, not a verified specification of the competitors' internal implementations. Do not present unverified assumptions as established facts.
>
> 3. Approved technical decisions. G1. Use gpt-6-luna with the course-provided API key, consistent with the final-project instructions. Do not silently substitute another model. G2. Investigate the available source of actual per-token pricing. Record real token counts from model responses. Do not invent prices or report projected costs as measured costs. G3. Reuse the existing HW5 architecture where appropriate (React, Vite, TypeScript; FastAPI and PydanticAI; SQLite and SQLAlchemy; pytest and Vitest). Inspect the existing implementation before copying or adapting code. G4. Prioritize a reproducible local application. A hosted demo is optional and should not compromise local reliability. G5. Implement user accounts and backend-enforced data isolation. Include tests proving that one user cannot access another user's data. G6. Use a locally available USDA-based nutrition dataset for the initial version. Defer Open Food Facts until the core functionality is working, unless you identify a compelling reason to include it earlier. G7. Apply user confirmation according to the type of action: routine generation (generate a complete workout; the user can review it but must not be required to approve every exercise); exercise replacement (user-initiated; the Training Agent suggests suitable alternatives; the user selects); workout execution and logging (no confirmation for every set); persistent changes (follow clear application rules and confirm when appropriate); AI safety (read-only operations need no confirmation; agents must not bypass backend authorization, validation, or explicit user constraints; ask for clarification or prevent unsafe actions). Venn must be practical, responsive, and easy to use. G8. Use a dedicated repository for the final project. Do not create a GitHub remote or publish the repository until the repository location and name are confirmed. G9. Maintain AI_prompts.md with significant development prompts and implementation milestones. G10. Make the evaluator's setup as simple as possible. Prefer a finished application that can run without requiring Node to build the frontend at runtime. Document any remaining prerequisites.
>
> 4. Agent architecture. Use the proposed specialized agents: Coach Router (routes free-form requests), Nutrition Agent, Training Agent (workout planning, exercise substitutions, training logs), Progress Coach (summarizes structured nutrition, training, and measurement data). Keep numerical calculations, authorization, input validation, workout constraints, and database operations in deterministic application code. Restrict each agent's tools according to its responsibilities. The Progress Coach must ground numerical claims in retrieved data or deterministic calculations. Do not invoke every agent for every request. Avoid unnecessary model calls.
>
> 5. Milestone 1: Foundation. Implement the first milestone only: the application skeleton and agreed architecture; a clean, responsive initial interface; database setup and schema migrations; user registration and login; backend-enforced user-data isolation; a profile and settings screen; user fitness goals and relevant training preferences; a calorie and macronutrient target calculator; explicit validation and safety minimums for target calculations; a seeded demo user; health checks for the application and AI connection; automated tests that pass without making network calls; a README with clear setup instructions; an .env.example file containing placeholder values only; an initial AI_prompts.md. The target calculator should use transparent formulas and validate its outputs. Do not present estimates as medical advice or claim that calculated targets are universally appropriate.
>
> 6. Evidence and quality requirements. Include tests for authentication and user-data isolation; test the target calculator against independent hand calculations; test invalid inputs and safety constraints; verify that the application can start without a working AI API connection, with AI functionality clearly disabled; keep secrets out of source control; document unresolved dependencies and limitations. Keep the application reproducible from a fresh clone, with a target setup time of ten minutes or less.
>
> 7. Development process. Work incrementally. Before making changes, inspect the relevant files and explain any architectural adjustments that are necessary. Implement only Milestone 1. After implementation, provide a summary of the changes, the files created or modified, the tests executed and their actual results, any unresolved issues, instructions for running the application, evidence that the setup works, and the recommended next milestone. Do not publish a GitHub repository or commit secrets. Proceed with Milestone 1.

**Result:** Milestone 1 implemented in this repository. See `docs/milestone1.md` for the scope, the adjustments to the architecture, and the limitations.

**Inputs read before coding:**
- *Final Project Instructions.pdf*. It requires `gpt-6-luna` only on the course key, and a `.env` lookup in the repo folder and then the folder above it.
- *Fitness App Competitive Audit.docx*.
- The HW5 code (`agents.py` Portkey wiring, frontend configuration).

## Prompt 3: Milestone 2, Nutrition Core (2026-10-25)

> Continue development of Venn in the existing `Final Project/venn/` directory. Milestone 1 is complete. **Preserve the existing architecture and functionality.** Inspect the current implementation before changing anything, and build on the existing authentication, database, API, UI, testing, and documentation. Our deadline is Monday, October 26, 2026, at 6:00 PM. Prioritize a coherent, functional end-to-end product over unnecessary complexity.
>
> **1. Product and implementation priorities.** Implement the Nutrition Core as a real, persistent, authenticated feature. Priority order: 1. Reliable food search and logging. 2. Accurate, deterministic nutritional calculations. 3. Timestamp-based chronological food log. 4. Visual daily nutrition dashboard. 5. Recently used foods. 6. Barcode lookup for a bundled sample of products. 7. Responsive, polished interface and visual previews. Do not implement workout functionality or additional AI agents in this milestone.
>
> **2. Food catalog and search.** Create or extend a bundled food catalog with reliable nutritional values and clear source attribution. Include: food name and relevant description; serving size and unit; calories; protein, carbohydrates, and fat; source attribution where available; barcode for products that have one. Use curated USDA-sourced food data where appropriate, along with a small sample of packaged products for barcode lookup. Do not invent nutritional values or present estimates as verified facts. Where information is unavailable, identify it clearly. Food search must work offline and must not require an external API. Search results should be easy to scan, and users should be able to select a food and adjust the quantity before logging it.
>
> **3. Food logging and timestamps.** Food entries must be organized by actual date and time, not restricted to breakfast, lunch, dinner, or snacks. Each entry should store: authenticated user ID; food ID or food description for a manual entry; quantity and unit; calculated calories, protein, carbohydrates, and fat; date and timestamp, including hour and minute; creation and update timestamps as appropriate. The interface should display the current day's entries chronologically. Requirements: support multiple entries at any time of day; allow users to edit quantities and timestamps; allow users to delete their own entries; preserve historical entries when catalog values are updated (don't silently rewrite previously logged nutrition); handle dates and local time consistently; make logging a food from the past straightforward by allowing timestamp editing; validate quantities and units before saving; prevent unauthorized access to another user's entries. Use deterministic calculations for all nutritional totals. Do not use an AI model to calculate nutrition.
>
> **4. Nutrition dashboard and visual design.** Build a visual dashboard based on persisted user data. Display: daily calorie target, consumed calories, and remaining calories; protein target, consumed protein, and remaining protein; carbohydrate and fat targets and progress where available; chronological food log for the selected day. Use horizontal progress bars for calories, protein, carbohydrates, and fat. The visualization should distinguish consumed amounts from remaining amounts, using a filled section and a lightly shaded remaining section. Handle these states correctly: no food logged; partially completed targets; exactly reaching a target; exceeding a target; missing or unavailable nutrition targets. Don't fabricate nutrition targets. If targets aren't available, show the available consumption data and explain that the target has not been configured. Keep the dashboard clean and easy to understand. The numbers and visualizations must reflect actual persisted entries, not hardcoded demo values.
>
> **5. Food logging interaction.** Daily dashboard: nutrition summary and progress bars; chronological list of food entries; a prominent `+` button fixed or anchored at the bottom center on mobile, without obstructing the content; a sensible equivalent on desktop. Add food: when the user opens the food-entry flow, make these options easy to access: 1. Recently used foods. 2. Search foods. 3. Enter or scan a barcode. 4. Enter food manually if appropriate. Recently used foods should be ordered sensibly and allow users to reuse a food quickly. Selecting a recent food or search result should lead to a simple quantity-entry step, followed by saving the entry. Avoid unnecessary confirmation screens. Use accessible labels and controls. Make the interface responsive across desktop and mobile sizes.
>
> **6. Barcode scanning.** Barcode lookup is important to the intended product experience. Implement a small but real barcode workflow: bundle a sample catalog of packaged products with their actual available barcode and nutritional data; allow users to enter a barcode manually; if camera-based scanning can be implemented reliably with the existing stack and within the deadline, add it (prefer a solution that works without an external service); if camera scanning cannot be completed reliably, deliver the working manual barcode lookup and clearly document that camera scanning remains a limitation. For a recognized barcode, display the matched product and nutrition information before logging it. For an unknown barcode, show a useful message and offer search or manual entry. Do not pretend a barcode was scanned or a product was recognized when it was not.
>
> **7. Authentication and data isolation.** Inspect Milestone 1's existing account implementation before making changes. Preserve working registration, login, logout, password hashing, server-side sessions, and backend-enforced data isolation. Determine whether email is already used as the account identifier. If it is, preserve it. If not, assess whether changing to email-based registration can be done safely without destabilizing the existing authentication system. Do not introduce complex email verification or password-recovery infrastructure unless it is straightforward and can be tested reliably before the deadline. Every nutrition record must be associated with the authenticated user. The backend must derive the user ID from the authenticated session, not trust a user ID supplied in a request. Test cross-user access, including direct requests using another user's record ID.
>
> **8. Input validation and nutrition plausibility.** Validate numeric quantities, units, and resulting nutrition totals. Detect clearly implausible quantities or totals and provide an understandable warning or correction flow. Do not silently save obviously invalid values. Avoid arbitrary limits that block legitimate large meals or bulk food logging. Allow users to correct the quantity or choose a more appropriate unit. Keep the validation deterministic and testable.
>
> **9. AI and token economics.** Do not call an AI model for routine food search, barcode lookup, nutritional calculations, or ordinary food logging. The professor's class slide provides these reference prices per million tokens: `gpt-6-luna` input $0.10, cached input $0.01, cache write $0.125, output $0.50; `gpt-6.1-sol` $2.00 / $0.10 / $2.50 / $10.00; `gpt-6-astra` $10.00 / $1.00 / $12.50 / $50.00. Treat these as the professor-provided reference prices, not independently verified current prices. Do not silently change them. If you find authoritative evidence that applicable prices differ, document the source and distinguish verified current pricing from the class reference. Keep `gpt-6-luna` as the default model for general AI activities. Reserve `gpt-6.1-sol` for specific tasks only when improved reasoning is likely to provide meaningful additional value. Do not introduce Sol into the nutrition workflow merely to use a more capable model. Continue measuring actual token usage where supported. Do not invent usage figures or prices.
>
> **10. Visual previews.** I want to review the product's key visuals without interrupting implementation. After the real nutrition interface is implemented: launch the app; capture a desktop screenshot showing the nutrition dashboard and chronological food log; capture a screenshot of the add-food experience, including recent foods and search or barcode lookup; save the screenshots in a clear location, such as `docs/evidence/`; report their exact paths and briefly explain what each screenshot demonstrates. Use screenshots of the actual implementation rather than creating disconnected mockups. If screenshot tooling is unavailable or would materially delay implementation, report that limitation and provide the simplest useful alternative.
>
> **11. Tests and acceptance criteria.** Add automated tests for: food search; barcode lookup for recognized and unrecognized barcodes; unit conversions and quantity handling; nutritional calculations; creating, editing, and deleting food entries; timestamp persistence and chronological ordering; daily aggregation and dashboard calculations; empty states and missing nutrition targets; over-target progress visualization logic; implausible quantities and invalid input; historical records remaining stable after catalog changes; recently used foods; cross-user data isolation; persistence across application restarts; existing Milestone 1 functionality remaining operational. Run the existing and new tests. Report actual results; do not claim tests passed unless they were executed.
>
> **12. Documentation and final report.** Update: README.md with setup and usage instructions; `AI_prompts.md` with the actual prompt used for this milestone and a brief explanation of AI assistance; `.env.example` only if required, using placeholders and never real secrets; relevant architecture or implementation documentation; milestone documentation and evidence paths. Ensure the app still starts from a fresh clone without requiring a model API key. Nutrition features must work offline. At completion, report: 1. What was implemented. 2. Files changed. 3. Tests executed and actual results. 4. How to run the app and test the nutrition workflow. 5. Screenshot paths. 6. Barcode functionality delivered and any limitations. 7. Known bugs or limitations. 8. Recommended next milestone, prioritizing the most valuable work remaining before the deadline. Do not publish to GitHub or create a remote unless the repository destination has already been explicitly confirmed. Keep the implementation focused, testable, and functional. Preserve the working foundation from Milestone 1.

**How AI helped:** Claude Code read the Milestone 1 code first, then designed and wrote the Nutrition Core.

- **Data:**
  - built the offline catalog from the USDA bulk downloads, using a reproducible script, `scripts/build_food_catalog.py`;
  - switched to the bulk file after the USDA API rate-limited `DEMO_KEY`.
- **Backend:** wrote the services (units, nutrition math, plausibility checks, barcodes, search) and the API.
- **Frontend:** wrote the nutrition page and the add-food and edit sheets.
- **Testing:**
  - wrote 40 backend and 20 frontend tests;
  - checked the app in a real browser, and found and fixed layout and label issues from the screenshots;
  - captured evidence screenshots with a headless-browser script.

**What the AI did not do:**
- **No AI inside the app's nutrition features:** no model is called for nutrition, and all values come from USDA data and deterministic code.

**Result:**
- **Milestone 2 is implemented.** See `docs/milestone2.md` for the scope, design decisions, tests, screenshot paths and limitations, and `docs/data_sources.md` for data attribution.
- **Tests:** 89 backend tests (including all 49 from Milestone 1) and 28 frontend tests pass.

## Prompt 4: Milestone 3, Training Core (2026-10-26)

> Continue developing Venn in the existing `Final Project/venn/` directory. Milestones 1 and 2 are complete. Preserve the existing authentication, nutrition functionality, database, API, UI, tests, and documentation. Inspect the current implementation before making changes. The deadline is Monday, October 26, 2026, at 6:00 PM. Optimize for a coherent, functional product and a successful submission, not maximum feature count.
>
> **1. Objective.** Implement a functional Training Core that connects naturally to the existing nutrition app. The essential user journey is: 1. Open Training. 2. Generate a complete workout using the user's profile and constraints. 3. Review the routine. 4. Replace an exercise if desired. 5. Start and log the workout. 6. Finish the session and record its actual duration. 7. View the completed workout in history. Do not destabilize Nutrition or authentication.
>
> **2. Workout generation.** Generate a complete workout based on: training goal; training experience; available equipment; session time budget; preferred training split and frequency; explicit user-reported limitations; relevant workout history, if available. Use the existing curated exercise catalog if one exists. Otherwise, create a compact, structured catalog with exercise names, movement patterns, training objectives, equipment requirements, relevant muscles, and necessary constraints. Each generated workout should contain: workout name and objective; estimated duration; exercises in order; sets and repetition targets, or duration where appropriate; rest recommendations; short exercise instructions; a brief explanation of how the workout fits the user's preferences and constraints. The result must be a complete routine the user can review as a whole. Do not ask the user to approve each exercise individually. Ensure that the generated routine respects the user's time budget as realistically as possible, including sets, rest periods, and reasonable transitions.
>
> **3. Deterministic constraints and safety.** Treat safety constraints as application rules, not merely prompt instructions. Before presenting or saving a generated routine, validate it against: equipment availability; user-reported limitations; required exercise attributes; session-duration constraints; any existing application rules relevant to workout generation. Do not diagnose injuries, infer medical conditions, or claim that an exercise is medically safe. Do not allow a model response to bypass backend restrictions. If a requested routine cannot be generated within the available constraints, explain the limitation and offer a reasonable alternative. Preserve the existing distinction between general fitness guidance and medical advice.
>
> **4. Exercise replacement.** Allow users to initiate a replacement for a specific exercise. Suggest alternatives that serve a similar training objective and are compatible with the user's equipment and reported limitations. Display the alternatives and let the user choose one. Do not replace the exercise silently. If an AI agent is available, it may help rank or explain appropriate alternatives, but deterministic validation must filter out incompatible exercises.
>
> **5. Workout logging.** Implement a persistent workout lifecycle: create or generate a workout; start the session; record exercise completion; log sets, repetitions, and weights where applicable; support appropriate units and conversions; record actual start and finish times; calculate actual session duration; complete the workout and preserve it in history. Avoid unnecessary confirmations during logging. Users should be able to distinguish planned values from actual logged values. Associate every record with the authenticated user. Derive user identity from the authenticated session and enforce data isolation on the backend. Persist workout history across application restarts.
>
> **6. Planned versus actual duration.** Record the estimated duration of each generated workout and the actual duration of completed sessions. Display the difference between planned and actual duration in the completed workout summary. Use this information as groundwork for future adaptation, but do not implement a complex optimization system in this milestone. Do not fabricate historical workout data. If demo data is needed, identify it as demo data.
>
> **7. AI and architecture.** For this milestone, use the existing model infrastructure and `gpt-6-luna` if AI is needed for workout generation or exercise alternatives. Do not use a more expensive model merely because it is available. The professor's class slide lists the following reference prices per million tokens: `gpt-6-luna`: $0.10 input, $0.01 cached input, $0.125 cache write, $0.50 output; `gpt-6.1-sol`: $2.00 input, $0.10 cached input, $2.50 cache write, $10.00 output; `gpt-6-astra`: $10.00 input, $1.00 cached input, $12.50 cache write, $50.00 output. These are class reference figures, not independently verified current prices. Preserve the distinction between reference prices and verified pricing. Do not invent token usage or costs. Keep the app functional without an API key. If AI is disabled or unavailable, provide a deterministic fallback workout generator using the curated exercise catalog and the same safety constraints. Do not attempt to build every AI agent in this milestone. Build only what is needed for a useful Training workflow, while keeping the implementation ready for the upcoming agent integration.
>
> **8. User interface.** Add a coherent Training interface consistent with the existing Venn design. Include: training dashboard; workout generation form or controls; complete generated-workout view; exercise replacement flow; active workout logging interface; completed workout summary; workout history. Keep the interaction efficient and responsive. Provide actual screenshots of the implemented interface, preferably: training dashboard; generated workout; active workout logging; completed workout summary. Save screenshots under `docs/evidence/` and report their exact paths. Use the actual app for screenshots; do not create disconnected mockups.
>
> **9. Tests.** Add automated tests for: workout generation; equipment restrictions; user-reported limitation enforcement; duration estimation; exercise replacement compatibility; workout start and completion; set and repetition logging; unit conversion; planned versus actual duration; history persistence; cross-user data isolation; AI-disabled fallback; existing Nutrition and authentication functionality. Run all relevant backend and frontend tests and report actual results. Do not claim tests passed unless they were executed.
>
> **10. Documentation and completion report.** Update: README.md; `AI_prompts.md`; relevant architecture and milestone documentation; evidence and screenshots. At completion, report: 1. Implemented functionality. 2. Files changed. 3. Actual test results. 4. How to run and demonstrate the workout lifecycle. 5. Screenshot paths. 6. Remaining limitations. 7. Any issues that threaten integration or the deadline. Do not publish to GitHub or create a remote unless the repository destination has already been explicitly confirmed. Keep this milestone focused. Once the essential workout lifecycle works, stop expanding Training and prepare for AI agent integration and final deliverables.

**How AI helped:** Claude Code read the Milestone 1–2 code first, then built the Training Core.

- **Exercise catalog:**
  - curated 80 exercises from free-exercise-db with a reproducible script;
  - added Venn's own tags: movement pattern, extra equipment, reps or time, unilateral, and loaded body areas.
- **Backend:**
  - wrote the deterministic generator and rules (compatibility, duration model, validation);
  - wrote the workout lifecycle API, and 29 backend and 9 frontend tests;
  - found and fixed a real time-zone bug in the nutrition day view, with a regression test.
- **Frontend:** built the Training UI (home, review, replace, logging with a rest timer, summary, history).
- **Evidence:** captured screenshots by running a real session in a headless browser.

**What the AI did not do:**
- **No AI in training:** the generator is deterministic, so Training makes no model calls and its token cost is $0. The demo workout history is generated by the same code and labelled as demo data.

**Result:**
- **Milestone 3 is implemented.** See `docs/milestone3.md`.
- **Tests:** 119 backend and 37 frontend tests pass.

## Prompt 5: Milestone 3.5, profile, units, onboarding and design refresh (2026-10-26)

A short, 90-minute time-boxed refinement before the AI agent milestone. The prompt asked for these, in priority order:

1. **Units:** unit switches beside the height, weight, goal-weight and body-fat fields, with immediate, drift-free conversion and compatibility with existing records.
2. **Wording:** direct onboarding questions and short Settings labels.
3. **Goals:** clearer weight goals (lose body fat, maintain, gain muscle and strength) with optional clarifications; optional target weight and date instead of the weekly-percentage control, without inventing a new calorie algorithm; protein preferences (Flexible, Balanced, High protein) shown in grams per day without invented scientific claims.
4. **Diet and body fat:** diet style about eating patterns, not macros; optional, explained body fat.
5. **Training:** primary and secondary training goals, including muscular endurance and cardio fitness; cardio frequency, duration and whether to include it; strength days kept separate from cardio; the next workout auto-generated in Training; the user can change the split.
6. **Onboarding:** a lightweight first-run questionnaire, if safe (one question per screen, progress bar, Back and Continue, saved to the profile, editable in Settings, never blocking existing users).
7. **Design:** a monochrome system with outlined grey and solid black navigation icons (house, chef's hat, dumbbell, stretching person), and consistent nutrition colours (calories blue, protein green, carbs purple, fat amber).
8. **Tests:** focused regression tests, without weakening existing ones.
9. **Handoff:** brief documentation and a handoff.

Do not create a GitHub remote. Report and slides take priority over further cosmetic work.

**How AI helped:** Claude Code inspected the profile, target and generator code first, and then:
- **Backend:** made only additive changes (migration 0004, optional fields), mapping the new user-facing choices onto the existing, tested calculator;
- **Frontend:** built the unit fields, the shared profile model, the Settings rewrite, the onboarding questionnaire, the auto-generated workout and split selector, and the design refresh;
- **Tests:** added 8 backend tests and new frontend tests, and updated 4 older frontend tests for the changed UI;
- **Evidence:** captured new screenshots.

**What the AI did not do:**
- **No new calorie algorithm:** the calorie formula is unchanged, and target weight and date only project.

**Result:** see `docs/milestone3_5.md`.
- **Tests:** 127 backend and 43 frontend tests pass.

## Prompt 6: Milestone 3.6, questionnaire, settings and protein logic (2026-10-26)

A time-boxed (60-90 min) final refinement before AI agent integration. The prompt asked for:

1. **Strength vs. cardio:** separate scheduling. "How many days a week would you like to strength train?" (1-7), then "How would you like to schedule your cardio?" (on strength days / separate days / mix / none), with follow-ups for cardio days and session length. No complex concurrent-training optimisation.
2. **Duration ranges:** 15-30 ... 105-120 min, plus more than 120 with custom 10- or 15-minute increments. Store the upper bound and never exceed it.
3. **Workout location:** "Where do you plan to work out?" with exactly six locations (commercial gym, strength gym, local gym, home / garage gym, minimal equipment, bodyweight / outdoors), each with a description and preset equipment that stays editable. The final equipment list is the source of truth. Sentence case.
4. **Protein review:** inspect and document the existing protein calculation (which weight it uses, how preferences map to multipliers, how goals, weight and units affect it, the calorie cap). Use reputable sports or clinical nutrition sources to choose a defensible reference weight. Don't invent formulas or treat BMI or self-reported body fat as definitive. Show g/kg or g/lb with a consistent stored multiplier. Don't call it a personalised clinical recommendation.
5. **Protein range:** a tolerance range (about +/-5%) around the unrounded target, with below / within / above messages and correct handling of missing targets and empty logs. Calories, carbs and fat unchanged.
6. **Eating pattern:** "Do you follow a particular eating pattern or have dietary restrictions?" with an explicit "No specific restrictions" option and "Other" with a text field, kept distinct from allergies or medical requirements.
7. **Exercise ability:** a short, skippable questionnaire (push-ups, pull-ups/chin-ups, dips; can't do one yet ... 15+, not sure), saved and editable. Use it only if practical, never as a complete strength assessment.
8. **Onboarding:** keep the one-question-per-screen flow, and don't force existing users through it.
9. **Tests:** focused tests for all of the above, without weakening existing ones.
10. **Documentation:** document the protein decision and its sources. No GitHub remote. Stop after this refinement; next is AI agents, then the report, slides and submission.

**How AI helped:** Claude Code inspected the protein code and documented its original behaviour, then:
- **Protein:** chose a conservative reference-weight rule (target weight only when deliberately losing with a lower target) based on cited sports-nutrition sources, and kept the multipliers and cap;
- **Range:** added the +/-5% range, computed in the backend from the unrounded target;
- **Profile:** added backward-compatible profile fields (migration 0005);
- **Interface:** extended onboarding and Settings, and used ability answers only to leave out bodyweight moves the user can't do yet;
- **Tests:** added 31 backend and 7 frontend tests, and updated 2 UI tests for the changed flow.

**Result:** see `docs/milestone3_6.md` and `docs/protein_review.md`.
- **Tests:** 158 backend and 50 frontend tests pass.

## Prompt 7: Milestone 4, AI Coach agents (2026-10-26)

Summary of the instructions. This was the final major implementation milestone, prioritising genuine agent functionality, tool use, measurable token economics, safety and evidence.

1. **Reuse:** inspect and reuse the existing model integration, pricing, usage logging, services and safety rules. Use `gpt-6-luna` only, and keep the app usable without a key.
2. **Agents:** a lightweight router plus three workflows:
   - **Nutrition Agent:** actual food logs; authoritative protein target, reference weight and range, never recalculated.
   - **Training Agent:** the existing generator and compatibility checks; read-only.
   - **Progress Coach:** cross-domain insights that separate observations from hypotheses and correlation from causation, with no fabrication.
3. **Tools:** genuine, narrowly scoped tools bound to the authenticated session; never trust a client or LLM user id; limit tool calls.
4. **Prompt injection:** a meaningful defence for user-written fields (data, not commands), enforced in code, with automated tests including an incompatible-exercise case.
5. **Usage:** record actual usage per call (workflow, model, input / cached / output tokens, timestamp, status, estimated cost at the professor's reference prices). No invented or double-counted tokens; measured costs distinguished from projections. Never use `gpt-6.1-sol` or `gpt-6-astra` on the course key.
6. **Traces and grounding:** run traces (workflow, tools, status, usage, cost, validations), plus deterministic grounding checks for numerical claims.
7. **AI-disabled:** a clear unavailable state; deterministic features keep working; no fake AI text; graceful timeouts.
8. **Screenshots:** of real runs (nutrition, training, progress, safety, trace).
9. **Tests:** router, permitted tools, grounding, workouts and compatibility, progress, missing data, injection, authorisation, token and cost maths, failures and timeouts, AI disabled, plus regressions. Mocked offline, with a few controlled live runs.
10. **Documentation and report:** update docs with an evidence table. No GitHub remote. Stop when the essentials work.

**How AI helped:** Claude Code:
- **Probing:** checked that a stateless tool-calling loop works with `gpt-6-luna` through Portkey;
- **Building:** wrote the router, eight read-only tools, the runner with allow-lists and limits, the safety layer (sanitising, numeric grounding, exercise guard), per-call usage and cost tracking with run traces, the Coach API and UI;
- **Testing:** wrote 28 backend and 3 frontend tests with a scripted fake model, then ran 6 live questions through the real UI, capturing screenshots and full run records.

All numbers shown to users come from deterministic tools. The model chooses tools and writes the explanation.

**Result:** see `docs/milestone4.md`.
- **Tests:** 186 backend and 53 frontend tests pass.
- **Live runs:** a six-question evaluation (runs 1–6), $0.00033 per question on average at the reference prices, plus one separate injection-defense run (#7).

## Prompt 8: Final deliverables (2026-10-26)

Summary of the instructions. Milestone 4 is the functional baseline; no new features or refactors unless a submission blocker requires it.

1. **Canvas:** submit only `report.html` (self-contained, 10–15 pages) and `slides.html` (self-contained, reveal.js, at most 10 slides), plus an optional video of the student testing the app. No ZIP, README, source or screenshots on Canvas.
2. **Repository link:** the GitHub URL must be prominent and clickable in both files, with its visibility stated.
3. **Report sections:** motivation and differentiation, architecture and agent design, tool use, token economics, safety and privacy, impact evaluation, limitations, AI-use disclosure; embedded screenshots.
4. **Honesty:** label measured, calculated and projected figures; explain the six-question evaluation and the additional injection-defense run without double-counting; no invented research, testimonials, results or citations; real user evidence only if it exists.
5. **Validation:** check staged files for secrets and unneeded files, `.env.example` placeholders only; run backend, frontend and fresh-clone tests; open both HTML files in a browser.
6. **Publishing:** confirm the repository name and visibility first (confirmed: `venn`, public).

**How AI helped:** Claude Code:
- ran a cost-optimisation experiment (`scripts/router_experiment.py`: keyword router vs. a gpt-6-luna router on 10 author-labelled questions);
- recaptured screenshots in the current design;
- wrote `deliverables/build.py`, which generates both HTML files from the evidence files (numbers are computed, not typed) and inlines screenshots and reveal.js;
- corrected the docs: cache-write tokens had been reported, and the six-question totals now cover runs 1–6 with run 7 separate.


## Prompt 9: Body dashboard, Progress and Recovery (2026-10-26)

Summary of the instructions. Deadline day: prioritise a functional, reliable feature over complexity, and reuse existing patterns without destabilising working code.

1. **Body section:** a segmented Progress / Recovery toggle; responsive, accessible and in Venn's design language.
2. **Progress:** dated body weight (latest, previous, difference, chart or list, kg/lb); waist, chest and hips measurements (biceps and thighs if easy) with comparison and deletion; validation of units, dates and implausible values; no body-fat inference and no fat-vs-muscle claims.
3. **Recovery:**
   - **Map:** front and back views with ten clickable muscle groups, coloured from real workout data, with a legend (grey not assessed; light, medium and dark red for low, moderate and high estimated fatigue).
   - **Indicators:** last-workout indicators and fatigue counts.
   - **Model:** deterministic, from logged workouts and existing mappings, with an insufficient-data state; thresholds documented as illustrative; primary vs. secondary muscles weighted.
   - **Detail panel:** per-group detail.
   - **Soreness:** an optional user-reported 0–10 rating, kept separate.
4. **Security and tests:** user-scoped everything, cross-user denial, and tests for CRUD, validation, units, empty states, comparisons, recovery boundaries, mapping, no history and soreness.
5. **AI Coach (optional):** narrowly scoped, read-only body access with no extra model calls; gpt-6-luna only.
6. **Deliverables and audit:** update the report, slides and README honestly, within 10–15 pages and 10 slides. Do not commit or push without authorisation.

**How AI helped:** Claude Code:
- **Backend:** added the `body_weight`, `body_measurement` and `soreness_rating` tables (migration 0007), the `/api/body/*` endpoints and `services/recovery.py`. The recovery service uses free-exercise-db primary muscles at 1.0 and secondary at 0.5, a 72-hour linear fade over a 7-day window, and fixed illustrative thresholds.
- **Frontend:** built the Body page with the toggle, the Progress view (weight chart, measurement comparison), the Recovery view (inline SVG front and back figures, legend, indicators, detail panel, soreness) and a body summary inside `get_progress_metrics`.
- **Tests:** wrote 40 backend and 6 frontend tests.
- **Deliverables:** regenerated the report and slides.

Details: `docs/milestone5.md`. Nothing was committed or pushed.
