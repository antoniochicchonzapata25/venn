import { type FormEvent, useState } from "react";
import { api, ApiError } from "../api";
import { label } from "../labels";
import type { Profile, Target } from "../types";

const fmt = (n: number | undefined, digits = 0) =>
  n == null ? "-" : n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export default function TargetsPanel({ target, profile, disclaimer, onChanged }: {
  target: Target | null; profile: Profile; disclaimer: string; onChanged: () => Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [manual, setManual] = useState({ kcal: "", protein_g: "", carb_g: "", fat_g: "" });
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const b = target?.breakdown ?? {};
  const macroKcal = 4 * Number(manual.protein_g || 0) + 4 * Number(manual.carb_g || 0) + 9 * Number(manual.fat_g || 0);

  function startEditing() {
    if (target) setManual({ kcal: String(target.kcal), protein_g: String(target.protein_g), carb_g: String(target.carb_g), fat_g: String(target.fat_g) });
    setErrors([]);
    setEditing(true);
  }

  async function saveManual(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors([]);
    try {
      await api.setManualTarget({
        kcal: Number(manual.kcal), protein_g: Number(manual.protein_g), carb_g: Number(manual.carb_g), fat_g: Number(manual.fat_g),
      });
      await onChanged();
      setEditing(false);
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not save targets."]);
    } finally {
      setBusy(false);
    }
  }

  async function useFormula() {
    if (target?.method === "manual" && !window.confirm("Replace your own targets with Venn's calculated targets?")) return;
    setBusy(true);
    try {
      await api.recalculate();
      await onChanged();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not recalculate."]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card stack" aria-label="Targets">
      <div className="card-head">
        <h2>Daily targets</h2>
        {target && <span className="pill">{target.method === "manual" ? "Set by you" : "Calculated"}</span>}
      </div>

      {!target ? (
        <p className="muted">Save your profile to calculate targets.</p>
      ) : (
        <>
          <div className="target-tiles">
            <div className="tile"><span className="tile-value" data-testid="target-kcal">{fmt(target.kcal)}</span><span className="muted small">kcal</span></div>
            <div className="tile"><span className="tile-value">{target.protein_g}</span><span className="muted small">protein g</span></div>
            <div className="tile"><span className="tile-value">{target.carb_g}</span><span className="muted small">carbs g</span></div>
            <div className="tile"><span className="tile-value">{target.fat_g}</span><span className="muted small">fat g</span></div>
          </div>

          {b.warnings?.map((w) => <div key={w} className="alert alert-warn small">{w}</div>)}

          {target.method === "formula" && (
            <details className="breakdown">
              <summary>How Venn calculated this</summary>
              <ol className="small">
                <li>Resting energy (Mifflin-St Jeor, {label("sex", profile.sex)}): <strong>{fmt(b.bmr, 1)} kcal</strong></li>
                <li>× activity factor {b.activity_multiplier} = maintenance <strong>{fmt(b.tdee, 1)} kcal</strong></li>
                <li>Goal adjustment: <strong>{(b.daily_energy_change ?? 0) > 0 ? "+" : ""}{fmt(b.daily_energy_change, 1)} kcal/day</strong>
                  {" "}({profile.goal_rate_pct}% of body weight per week × 7,700 kcal/kg ÷ 7)</li>
                <li>Safety minimum: {fmt(b.minimum_kcal, 1)} kcal {b.minimum_applied ? "(applied)" : "(not needed)"}</li>
                <li>Protein {label("protein_level", profile.protein_level)}{b.protein_capped ? ", capped at 35% of calories" : ""};
                  fat {label("diet_style", profile.diet_style)}; carbs fill the rest.</li>
                <li>Estimated change at these targets: <strong>{fmt(b.estimated_weekly_change_kg, 2)} kg/week</strong></li>
              </ol>
            </details>
          )}
        </>
      )}

      {editing ? (
        <form onSubmit={saveManual} className="stack" aria-label="Manual targets">
          <div className="row row-4">
            {(["kcal", "protein_g", "carb_g", "fat_g"] as const).map((k) => (
              <label className="field" key={k}>
                <span>{{ kcal: "Calories", protein_g: "Protein g", carb_g: "Carbs g", fat_g: "Fat g" }[k]}</span>
                <input id={`manual_${k}`} type="number" min={0} value={manual[k]}
                       onChange={(e) => setManual((m) => ({ ...m, [k]: e.target.value }))} required />
              </label>
            ))}
          </div>
          <p className="muted small">Macros add up to {fmt(macroKcal)} kcal (must be within 10% of your calories).</p>
          {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
          <div className="btn-row">
            <button className="btn btn-primary" disabled={busy}>Save my targets</button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="btn-row">
          <button type="button" className="btn btn-ghost btn-sm" onClick={startEditing} disabled={!profile.is_complete}>Set my own targets</button>
          {target?.method === "manual" && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={useFormula} disabled={busy}>Use calculated targets</button>
          )}
          {!editing && errors.length > 0 && <div className="alert alert-error" role="alert">{errors.join(" ")}</div>}
        </div>
      )}
      <p className="disclaimer small">{disclaimer}</p>
    </section>
  );
}
