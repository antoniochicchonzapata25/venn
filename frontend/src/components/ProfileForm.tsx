import { type FormEvent, type ReactNode, useState } from "react";
import { api, ApiError } from "../api";
import {
  ABILITY_EXERCISES, ABILITY_LEVELS, ACTIVITY_CHOICES, CARB_FAT_CHOICES, CARDIO_MINUTES, CARDIO_SCHEDULE_CHOICES, type Choice,
  CUSTOM_DURATIONS, DIETARY_REQUIREMENTS, DURATION_CHOICES, durationLabel, EATING_PATTERN_CHOICES, EXPERIENCE_CHOICES,
  fromProfile, GOAL_CHOICES, goalFields, GYM_LOCATIONS, hasScaleGoal, type Model, PACE_CHOICES, PROTEIN_CHOICES, proteinGrams,
  proteinPerUnit, proteinReferenceKg, SEX_CHOICES, SPLIT_CHOICES, TRAINING_GOAL_CHOICES, toInput,
} from "../profileModel";
import type { Options, Profile, Target } from "../types";
import { formatWeight } from "../units";
import { HeightField, WeightField } from "./UnitFields";

/** Compact select whose chosen option's description is shown underneath. */
export function ChoiceSelect({ id, label, value, choices, onChange, optional, placeholder = "Choose…", emptyLabel = "None" }: {
  id: string; label: ReactNode; value: string; choices: Choice[]; onChange: (v: string) => void; optional?: boolean;
  placeholder?: string; emptyLabel?: string;
}) {
  const chosen = choices.find((c) => c.id === value);
  return (
    <label className="field">
      <span>{label}</span>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} required={!optional}>
        {(value === "" || optional) && <option value="">{optional ? emptyLabel : placeholder}</option>}
        {choices.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select>
      {chosen?.description && <small className="muted">{chosen.description}</small>}
    </label>
  );
}

export default function ProfileForm({ profile, options, onSaved }: {
  profile: Profile; options: Options; onSaved: (p: Profile, t: Target | null) => void;
}) {
  const [m, setM] = useState<Model>(() => fromProfile(profile));
  const [errors, setErrors] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Model>(k: K) => (v: Model[K]) => setM((x) => ({ ...x, [k]: v }));
  const toggle = (k: "equipment" | "dietary_preferences", v: string) =>
    set(k)(m[k].includes(v) ? m[k].filter((x) => x !== v) : [...m[k], v]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErrors([]);
    setNotice(null);
    setBusy(true);
    try {
      const res = await api.saveProfile(toInput(m));
      onSaved(res.profile, res.target);
      setM(fromProfile(res.profile));
      setNotice(res.target_updated
        ? "Saved. Your calculated targets were updated."
        : "Saved. Your own targets were kept; use “Use calculated targets” to switch back.");
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not save. Please try again."]);
    } finally {
      setBusy(false);
    }
  }

  const proj = profile.goal_projection;
  const refKg = proteinReferenceKg({ weight_kg: m.weight_kg, target_weight_kg: m.target_weight_kg, losing: goalFields(m).goal === "lose" });
  const grams = proteinGrams(refKg, m.protein_level);
  const durationOptions: Choice[] = DURATION_CHOICES.filter((c) => c.id !== "custom")
    .concat(CUSTOM_DURATIONS.map((d) => ({ id: d, label: `${d} minutes (custom)` })));
  if (m.session_minutes && !durationOptions.some((c) => c.id === m.session_minutes)) {
    durationOptions.push({ id: m.session_minutes, label: durationLabel(m.session_minutes) });
  }
  const preset = GYM_LOCATIONS.find((g) => g.id === m.gym_location);

  return (
    <form className="card stack" onSubmit={submit} aria-label="Profile">
      <h2>Body</h2>
      <div className="row">
        <ChoiceSelect id="sex" label="Sex (for the energy formula)" value={m.sex} choices={SEX_CHOICES} onChange={set("sex")} />
        <label className="field"><span>Birth year</span>
          <input id="birth_year" type="number" inputMode="numeric" value={m.birth_year} onChange={(e) => set("birth_year")(e.target.value)} required min={1900} max={2100} />
        </label>
      </div>
      <div className="row">
        <HeightField id="height" cm={m.height_cm} unit={m.height_unit} onCm={set("height_cm")} onUnit={set("height_unit")} />
        <WeightField id="weight" label="Weight" kg={m.weight_kg} unit={m.weight_unit} onKg={set("weight_kg")} onUnit={set("weight_unit")} required />
      </div>
      <div className="row">
        <label className="field"><span>Body fat % <em className="muted">(optional)</em></span>
          <input id="body_fat" type="number" inputMode="decimal" step="0.1" min="3" max="60" value={m.body_fat_pct}
                 onChange={(e) => set("body_fat_pct")(e.target.value)} />
          <small className="muted">Only if you know it, e.g. from a scan. Not used in calculations yet.</small>
        </label>
        <ChoiceSelect id="activity_level" label="Daily activity" value={m.activity_level} choices={ACTIVITY_CHOICES} onChange={set("activity_level")} />
      </div>

      <h2>Goal</h2>
      <ChoiceSelect id="goal" label="Goal" value={m.goalChoice} choices={GOAL_CHOICES} onChange={(v) => set("goalChoice")(v as Model["goalChoice"])} />
      {m.goalChoice === "lose_fat" && (
        <label className="field check"><input type="checkbox" checked={m.changeScale} onChange={(e) => set("changeScale")(e.target.checked)} />
          <span>I also want to lose scale weight <small className="muted">(untick to keep your weight about the same)</small></span></label>
      )}
      {m.goalChoice === "gain_muscle" && (
        <label className="field check"><input type="checkbox" checked={!m.changeScale} onChange={(e) => set("changeScale")(!e.target.checked)} />
          <span>Keep weight changes minimal <small className="muted">(eat at maintenance instead of a surplus)</small></span></label>
      )}
      {hasScaleGoal(m) && (
        <>
          <ChoiceSelect id="pace" label="Pace" value={m.pace} choices={PACE_CHOICES} onChange={(v) => set("pace")(v as Model["pace"])} />
          <div className="row">
            <WeightField id="target_weight" label="Target weight (optional)" kg={m.target_weight_kg} unit={m.weight_unit}
                         onKg={set("target_weight_kg")} onUnit={set("weight_unit")} />
            <label className="field"><span>Target date <em className="muted">(optional)</em></span>
              <input id="target_date" type="date" value={m.target_date} onChange={(e) => set("target_date")(e.target.value)} />
            </label>
          </div>
          {proj && (
            <div className="alert alert-info small" role="note">
              {proj.weeks_at_pace != null && <>At this pace (about {formatWeight(proj.weekly_change_kg ?? 0, m.weight_unit)} a week), reaching {formatWeight(proj.target_weight_kg, m.weight_unit)} takes about {proj.weeks_at_pace} weeks (around {proj.estimated_date}). </>}
              {proj.date_check}
            </div>
          )}
        </>
      )}

      <h2>Nutrition</h2>
      <ChoiceSelect id="protein_level" label="Protein" value={m.protein_level} choices={PROTEIN_CHOICES} onChange={set("protein_level")} />
      {grams && <p className="muted small protein-note">About <strong>{grams} g of protein a day</strong> ({proteinPerUnit(PROTEIN_CHOICES.find((c) => c.id === m.protein_level)?.gPerKg ?? 0, m.weight_unit)} of your {refKg !== m.weight_kg ? "target" : "current"} weight; capped at 35% of calories). Your daily goal is shown as a range of ±5%.</p>}
      <div className="row">
        <ChoiceSelect id="eating_pattern" label="Eating pattern" optional emptyLabel="Not answered" value={m.eating_pattern} choices={EATING_PATTERN_CHOICES} onChange={set("eating_pattern")} />
        {m.eating_pattern === "other" && (
          <label className="field"><span>Describe it</span>
            <input id="eating_pattern_other" maxLength={120} value={m.eating_pattern_other} onChange={(e) => set("eating_pattern_other")(e.target.value)} />
          </label>
        )}
      </div>
      <fieldset className="chips">
        <legend>Dietary requirements <span className="muted small">(optional)</span></legend>
        {(options.dietary_preferences.length ? DIETARY_REQUIREMENTS.filter((d) => options.dietary_preferences.includes(d.id)) : DIETARY_REQUIREMENTS).map((d) => (
          <label key={d.id} className={m.dietary_preferences.includes(d.id) ? "chip on" : "chip"}>
            <input type="checkbox" checked={m.dietary_preferences.includes(d.id)} onChange={() => toggle("dietary_preferences", d.id)} />
            {d.label}
          </label>
        ))}
      </fieldset>
      <ChoiceSelect id="diet_style" label="Carb / fat balance" value={m.diet_style} choices={CARB_FAT_CHOICES} onChange={set("diet_style")} />

      <h2>Training</h2>
      <div className="row">
        <ChoiceSelect id="training_goal" label="Primary goal" value={m.training_goal} choices={TRAINING_GOAL_CHOICES} onChange={set("training_goal")} />
        <ChoiceSelect id="secondary_training_goal" label="Secondary goal" optional value={m.secondary_training_goal}
                      choices={TRAINING_GOAL_CHOICES.filter((c) => c.id !== m.training_goal)} onChange={set("secondary_training_goal")} />
      </div>
      <div className="row">
        <ChoiceSelect id="experience" label="Experience" value={m.experience} choices={EXPERIENCE_CHOICES} onChange={set("experience")} />
        <ChoiceSelect id="preferred_split" label="Training split" value={m.preferred_split} choices={SPLIT_CHOICES} onChange={set("preferred_split")} />
      </div>
      <div className="row">
        <ChoiceSelect id="days_per_week" label="Strength days / week" value={m.days_per_week} onChange={set("days_per_week")}
                      choices={["1", "2", "3", "4", "5", "6", "7"].map((d) => ({ id: d, label: d }))} />
        <ChoiceSelect id="session_minutes" label="Duration" value={m.session_minutes} onChange={set("session_minutes")} choices={durationOptions} />
      </div>
      <div className="row">
        <ChoiceSelect id="gym_location" label="Workout location" value={m.gym_location} choices={GYM_LOCATIONS} onChange={set("gym_location")} optional emptyLabel="Not answered" />
        {preset && (
          <div className="field preset-btn">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => set("equipment")([...preset.equipment])}>Use {preset.label.toLowerCase()} equipment</button>
            <small className="muted">Replaces the selection below; you can still adjust it.</small>
          </div>
        )}
      </div>
      <fieldset className="chips">
        <legend>Equipment</legend>
        {options.equipment.map((eq) => (
          <label key={eq} className={m.equipment.includes(eq) ? "chip on" : "chip"}>
            <input type="checkbox" checked={m.equipment.includes(eq)} onChange={() => toggle("equipment", eq)} />
            {eq}
          </label>
        ))}
      </fieldset>
      <ChoiceSelect id="cardio_schedule" label="Cardio" optional emptyLabel="Not answered" value={m.cardio_schedule} choices={CARDIO_SCHEDULE_CHOICES}
                    onChange={(v) => setM((x) => ({ ...x, cardio_schedule: v, cardio_sessions_per_week: v === "none" ? "0" : x.cardio_sessions_per_week }))} />
      {m.cardio_schedule && m.cardio_schedule !== "none" && (
        <div className="row">
          <ChoiceSelect id="cardio_sessions" label="Cardio days / week" value={m.cardio_sessions_per_week} onChange={set("cardio_sessions_per_week")}
                        choices={["1", "2", "3", "4", "5", "6", "7"].map((d) => ({ id: d, label: d }))} />
          <ChoiceSelect id="cardio_minutes" label="Cardio duration" value={m.cardio_minutes} onChange={set("cardio_minutes")}
                        choices={CARDIO_MINUTES.map((d) => ({ id: d, label: `${d} minutes` }))} />
        </div>
      )}
      <fieldset className="ability">
        <legend>Bodyweight ability <span className="muted small">(reps with good form; optional)</span></legend>
        <div className="row row-3">
          {ABILITY_EXERCISES.map((ex) => (
            <ChoiceSelect key={ex.id} id={`ability_${ex.id}`} label={ex.label} optional emptyLabel="Not answered" value={m.exercise_ability[ex.id] ?? ""} choices={ABILITY_LEVELS}
                          onChange={(v) => { const next = { ...m.exercise_ability }; if (v) next[ex.id] = v; else delete next[ex.id]; set("exercise_ability")(next); }} />
          ))}
        </div>
      </fieldset>

      {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
      {notice && <div className="alert alert-ok" role="status">{notice}</div>}
      <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button>
    </form>
  );
}
