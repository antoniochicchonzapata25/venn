import { type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { HeightField, WeightField } from "../components/UnitFields";
import {
  ABILITY_EXERCISES, ABILITY_LEVELS, ACTIVITY_CHOICES, CARDIO_MINUTES, CARDIO_SCHEDULE_CHOICES, type Choice, CUSTOM_DURATIONS,
  DURATION_CHOICES, durationChoiceId, EATING_PATTERN_CHOICES, emptyModel, EXPERIENCE_CHOICES, fromProfile, GOAL_CHOICES,
  goalFields, GYM_LOCATIONS, hasScaleGoal, type Model, PACE_CHOICES, PROTEIN_CHOICES, proteinGrams, proteinPerUnit,
  proteinReferenceKg, SEX_CHOICES, TRAINING_GOAL_CHOICES, toInput,
} from "../profileModel";
import type { Options } from "../types";

function Cards({ name, value, choices, onPick }: { name: string; value: string; choices: Choice[]; onPick: (v: string) => void }) {
  return (
    <div className="choice-cards" role="radiogroup" aria-label={name}>
      {choices.map((c) => (
        <button key={c.id} type="button" role="radio" aria-checked={value === c.id}
                className={value === c.id ? "choice-card on" : "choice-card"} onClick={() => onPick(c.id)}>
          <strong>{c.label}</strong>
          {c.description && <span className="muted small">{c.description}</span>}
        </button>
      ))}
    </div>
  );
}

interface Step { id: string; question: string; hint?: string; show?: (m: Model) => boolean; valid: (m: Model) => boolean; body: () => ReactNode }

/** First-run questionnaire: one question per screen, saved to the existing profile at the end. */
export default function Onboarding() {
  const navigate = useNavigate();
  const [m, setM] = useState<Model>(emptyModel());
  const [options, setOptions] = useState<Options | null>(null);
  const [index, setIndex] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Model>(k: K) => (v: Model[K]) => setM((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    api.profile().then((p) => setM(fromProfile(p))).catch(() => undefined);
    api.options().then(setOptions).catch(() => undefined);
  }, []);

  const currentYear = new Date().getFullYear();
  const steps: Step[] = [
    { id: "goal", question: "What's your main goal right now?", valid: (x) => x.goalChoice !== "",
      body: () => <Cards name="Goal" value={m.goalChoice} choices={GOAL_CHOICES} onPick={(v) => setM((x) => ({ ...x, goalChoice: v as Model["goalChoice"], changeScale: true }))} /> },
    { id: "scale", question: m.goalChoice === "lose_fat" ? "Do you also want to lose scale weight?" : "Would you rather keep weight changes minimal?",
      show: (x) => x.goalChoice === "lose_fat" || x.goalChoice === "gain_muscle", valid: () => true,
      body: () => m.goalChoice === "lose_fat" ? (
        <Cards name="Scale weight" value={m.changeScale ? "yes" : "no"} onPick={(v) => set("changeScale")(v === "yes")} choices={[
          { id: "yes", label: "Yes, I want the scale to go down", description: "Venn sets a calorie deficit." },
          { id: "no", label: "No, keep my weight about the same", description: "Eat at maintenance and let training change your shape." }]} />
      ) : (
        <Cards name="Weight change" value={m.changeScale ? "no" : "yes"} onPick={(v) => set("changeScale")(v === "no")} choices={[
          { id: "no", label: "I'm fine gaining some weight", description: "Venn sets a small calorie surplus." },
          { id: "yes", label: "Keep my weight about the same", description: "Eat at maintenance; progress is slower." }]} />
      ) },
    { id: "pace", question: "How quickly would you like to go?", show: hasScaleGoal, valid: () => true,
      hint: "You can add a target weight and date. Venn shows how long your pace would take; your calorie target still follows the pace you choose.",
      body: () => (
        <div className="stack">
          <Cards name="Pace" value={m.pace} choices={PACE_CHOICES} onPick={(v) => set("pace")(v as Model["pace"])} />
          <div className="row">
            <WeightField id="ob_target" label="Target weight (optional)" kg={m.target_weight_kg} unit={m.weight_unit} onKg={set("target_weight_kg")} onUnit={set("weight_unit")} />
            <label className="field"><span>Target date (optional)</span>
              <input type="date" value={m.target_date} onChange={(e) => set("target_date")(e.target.value)} /></label>
          </div>
        </div>
      ) },
    { id: "about", question: "A little about you", hint: "Used only for the energy formula.", valid: (x) => !!x.sex && Number(x.birth_year) > 1900,
      body: () => (
        <div className="stack">
          <Cards name="Sex" value={m.sex} choices={SEX_CHOICES} onPick={set("sex")} />
          <label className="field"><span>What year were you born?</span>
            <input id="ob_birth" type="number" inputMode="numeric" min={1920} max={currentYear - 18} value={m.birth_year} onChange={(e) => set("birth_year")(e.target.value)} /></label>
        </div>
      ) },
    { id: "size", question: "How tall are you, and what do you weigh?", valid: (x) => !!x.height_cm && !!x.weight_kg,
      body: () => (
        <div className="row">
          <HeightField id="ob_height" cm={m.height_cm} unit={m.height_unit} onCm={set("height_cm")} onUnit={set("height_unit")} />
          <WeightField id="ob_weight" label="Weight" kg={m.weight_kg} unit={m.weight_unit} onKg={set("weight_kg")} onUnit={set("weight_unit")} />
        </div>
      ) },
    { id: "activity", question: "How active are you outside your planned workouts?", valid: (x) => !!x.activity_level,
      body: () => <Cards name="Daily activity" value={m.activity_level} choices={ACTIVITY_CHOICES} onPick={set("activity_level")} /> },
    { id: "tgoal", question: "What do you most want from training?", hint: "Pick one. You can add a secondary goal in Settings.", valid: (x) => !!x.training_goal,
      body: () => <Cards name="Training goal" value={m.training_goal} choices={TRAINING_GOAL_CHOICES} onPick={set("training_goal")} /> },
    { id: "experience", question: "How would you describe your training experience?", valid: (x) => !!x.experience,
      body: () => <Cards name="Experience" value={m.experience} choices={EXPERIENCE_CHOICES} onPick={set("experience")} /> },
    { id: "days", question: "How many days a week would you like to strength train?", hint: "Strength sessions only. You'll be asked about cardio separately.", valid: (x) => !!x.days_per_week,
      body: () => <Cards name="Strength days" value={m.days_per_week} onPick={set("days_per_week")}
                         choices={["1", "2", "3", "4", "5", "6", "7"].map((d) => ({ id: d, label: d === "1" ? "1 day" : `${d} days` }))} /> },
    { id: "minutes", question: "How much time do you usually have per workout?", hint: "Venn uses the top of the range as your limit and keeps every workout within it, including warm-up and rest.",
      valid: (x) => !!x.session_minutes,
      body: () => (
        <div className="stack">
          <Cards name="Duration" value={durationChoiceId(m.session_minutes)} choices={DURATION_CHOICES}
                 onPick={(v) => set("session_minutes")(v === "custom" ? "135" : v)} />
          {Number(m.session_minutes) > 120 && (
            <label className="field"><span>How long, in total?</span>
              <select id="ob_custom_minutes" value={m.session_minutes} onChange={(e) => set("session_minutes")(e.target.value)}>
                {CUSTOM_DURATIONS.map((d) => <option key={d} value={d}>{d} minutes</option>)}
              </select>
            </label>
          )}
        </div>
      ) },
    { id: "location", question: "Where do you plan to work out?", hint: "This pre-selects equipment. Adjust the list to match what you actually have.",
      valid: (x) => !!x.gym_location,
      body: () => (
        <div className="stack">
          <Cards name="Workout location" value={m.gym_location} choices={GYM_LOCATIONS}
                 onPick={(v) => setM((x) => ({ ...x, gym_location: v, equipment: [...(GYM_LOCATIONS.find((g) => g.id === v)?.equipment ?? [])] }))} />
          {m.gym_location && (
            <fieldset className="chips">
              <legend>Your equipment <span className="muted small">(body weight is always included)</span></legend>
              {(options?.equipment ?? []).filter((e) => e !== "body only").map((eq) => (
                <label key={eq} className={m.equipment.includes(eq) ? "chip on" : "chip"}>
                  <input type="checkbox" checked={m.equipment.includes(eq)}
                         onChange={() => set("equipment")(m.equipment.includes(eq) ? m.equipment.filter((x) => x !== eq) : [...m.equipment, eq])} />
                  {eq}
                </label>
              ))}
            </fieldset>
          )}
        </div>
      ) },
    { id: "cardio", question: "How would you like to schedule your cardio?", valid: (x) => !!x.cardio_schedule,
      body: () => <Cards name="Cardio schedule" value={m.cardio_schedule} choices={CARDIO_SCHEDULE_CHOICES}
                         onPick={(v) => setM((x) => ({ ...x, cardio_schedule: v, cardio_sessions_per_week: v === "none" ? "0" : x.cardio_sessions_per_week === "0" ? "" : x.cardio_sessions_per_week }))} /> },
    { id: "cardio_days", question: "How many days a week would you like to do cardio?", show: (x) => !!x.cardio_schedule && x.cardio_schedule !== "none",
      valid: (x) => Number(x.cardio_sessions_per_week) > 0,
      body: () => <Cards name="Cardio days" value={m.cardio_sessions_per_week} onPick={set("cardio_sessions_per_week")}
                         choices={["1", "2", "3", "4", "5", "6", "7"].map((d) => ({ id: d, label: d === "1" ? "1 day" : `${d} days` }))} /> },
    { id: "cardio_minutes", question: "How long would you like each cardio session to last?", show: (x) => !!x.cardio_schedule && x.cardio_schedule !== "none",
      valid: (x) => !!x.cardio_minutes,
      body: () => <Cards name="Cardio duration" value={m.cardio_minutes} onPick={set("cardio_minutes")}
                         choices={CARDIO_MINUTES.map((d) => ({ id: d, label: `${d} minutes` }))} /> },
    { id: "ability", question: "How many reps can you do with good form?", hint: "Optional. Answer from experience; don't test yourself to failure. This helps Venn pick suitable variations.",
      valid: () => true,
      body: () => (
        <div className="stack">
          {ABILITY_EXERCISES.map((ex) => (
            <label key={ex.id} className="field"><span>{ex.label}</span>
              <select id={`ob_ability_${ex.id}`} value={m.exercise_ability[ex.id] ?? ""}
                      onChange={(e) => set("exercise_ability")({ ...m.exercise_ability, [ex.id]: e.target.value || "unsure" })}>
                <option value="">Skip</option>
                {ABILITY_LEVELS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </label>
          ))}
        </div>
      ) },
    { id: "protein", question: "What level of protein intake feels realistic for you?", valid: (x) => !!x.protein_level,
      body: () => {
        const ref = proteinReferenceKg({ weight_kg: m.weight_kg, target_weight_kg: m.target_weight_kg, losing: goalFields(m).goal === "lose" });
        return (
          <div className="stack">
            <Cards name="Protein" value={m.protein_level} onPick={set("protein_level")} choices={PROTEIN_CHOICES.map((c) => ({
              ...c, description: `${c.description} ${proteinPerUnit(c.gPerKg, m.weight_unit)}${ref ? `, about ${proteinGrams(ref, c.id)} g a day` : ""}.` }))} />
            <p className="muted small">
              {ref && ref !== m.weight_kg ? "Based on your target weight, because you're aiming to lose weight. " : "Based on your current weight. "}
              General guidance for active adults, not a personalised clinical recommendation. Venn caps protein at 35% of your calories, and your daily goal is shown as a range.
            </p>
          </div>
        );
      } },
    { id: "diet", question: "Do you follow a particular eating pattern or have dietary restrictions?", valid: (x) => !!x.eating_pattern && (x.eating_pattern !== "other" || !!x.eating_pattern_other.trim()),
      body: () => (
        <div className="stack">
          <Cards name="Eating pattern" value={m.eating_pattern} choices={EATING_PATTERN_CHOICES} onPick={set("eating_pattern")} />
          {m.eating_pattern === "other" && (
            <label className="field"><span>Tell us more</span>
              <input id="ob_pattern_other" maxLength={120} value={m.eating_pattern_other} onChange={(e) => set("eating_pattern_other")(e.target.value)} />
            </label>
          )}
          <p className="muted small">Allergies and other dietary requirements (dairy-free, gluten-free, nut-free, halal, kosher) can be added in Settings.</p>
        </div>
      ) },
  ];
  const visible = steps.filter((s) => !s.show || s.show(m));
  const i = Math.min(index, visible.length - 1);
  const step = visible[i];
  const last = i === visible.length - 1;

  async function finish() {
    setBusy(true);
    setErrors([]);
    try {
      await api.saveProfile(toInput(m));
      navigate("/", { replace: true });
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not save. Please try again."]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page onboarding">
      <div className="ob-top">
        <span className="muted small">Question {i + 1} of {visible.length}</span>
        <Link to="/" className="link small">Skip for now</Link>
      </div>
      <div className="ob-progress" role="progressbar" aria-label="Setup progress" aria-valuemin={1} aria-valuemax={visible.length} aria-valuenow={i + 1}>
        <div style={{ width: `${((i + 1) / visible.length) * 100}%` }} />
      </div>
      <section className="card stack ob-card" aria-label={step.question}>
        <h1>{step.question}</h1>
        {step.hint && <p className="muted">{step.hint}</p>}
        {step.body()}
        {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
        <div className="btn-row spread">
          <button type="button" className="btn btn-ghost" disabled={i === 0} onClick={() => setIndex(i - 1)}>Back</button>
          {last ? (
            <button type="button" className="btn btn-primary" disabled={busy || !step.valid(m)} onClick={finish}>{busy ? "Saving…" : "Finish"}</button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={!step.valid(m)} onClick={() => setIndex(i + 1)}>Continue</button>
          )}
        </div>
      </section>
      <p className="muted small">You can change any answer later in Settings. Report injuries or limitations there too.</p>
    </div>
  );
}
