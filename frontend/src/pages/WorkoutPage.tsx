import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { clock, differenceText, formatDateTime, fromKg, nextSetDefaults, restText, targetText } from "../training/logic";
import ReplaceSheet from "../training/ReplaceSheet";
import type { Workout, WorkoutExercise } from "../types";

/** One workout: review (planned) -> log (in progress) -> summary (completed). */
export default function WorkoutPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [w, setW] = useState<Workout | null>(null);
  const [unit, setUnit] = useState<"kg" | "lb">("kg");
  const [error, setError] = useState<string | null>(null);
  const [swap, setSwap] = useState<WorkoutExercise | null>(null);
  const [busy, setBusy] = useState(false);
  const [rest, setRest] = useState<{ until: number; total: number } | null>(null);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(() => api.workout(Number(id)).then(setW).catch((e) => setError(e instanceof ApiError ? e.message : "Could not load workout.")), [id]);
  useEffect(() => { load(); api.trainingOptions().then((o) => setUnit(o.units)).catch(() => undefined); }, [load]);
  useEffect(() => {
    if (w?.status !== "in_progress") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [w?.status]);

  async function act(fn: () => Promise<Workout | void>) {
    setBusy(true);
    setError(null);
    try {
      const out = await fn();
      if (out) setW(out);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !w) return <div className="page"><div className="alert alert-error">{error}</div><Link to="/training">Back to Training</Link></div>;
  if (!w) return <div className="page muted">Loading…</div>;

  const elapsed = w.started_at ? (now - new Date(w.started_at).getTime()) / 1000 : 0;
  const restLeft = rest ? (rest.until - now) / 1000 : 0;

  return (
    <div className="page workout-page">
      <Link to="/training" className="link small">‹ Training</Link>
      <header className="page-head">
        <div>
          <h1>{w.name} {w.is_demo && <span className="pill pill-muted">Demo data</span>}</h1>
          <p className="muted">{w.objective}</p>
        </div>
        <div className="workout-meta">
          {w.status === "planned" && <span className="pill">Planned · about {w.planned_minutes} of {w.budget_minutes} min</span>}
          {w.status === "in_progress" && <span className="pill pill-ok timer" aria-label="Elapsed time">⏱ {clock(elapsed)} <span className="muted">/ ~{w.planned_minutes} min</span></span>}
          {w.status === "completed" && <span className="pill pill-ok">Completed</span>}
        </div>
      </header>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {w.warnings && w.warnings.length > 0 && <div className="alert alert-warn small">{w.warnings.join(" ")}</div>}

      {w.status === "completed" && w.summary && <SummaryCard w={w} unit={unit} />}

      {w.status === "planned" && (
        <section className="card stack" aria-label="Why this workout">
          <h2>Why this workout</h2>
          <ul className="why-list small">{w.explanation.map((x) => <li key={x}>{x}</li>)}</ul>
          <div className="btn-row">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act(() => api.startWorkout(w.id))}>Start workout</button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => act(async () => {
              const fresh = await api.generateWorkout({ day_type: w.day_type, minutes: w.budget_minutes, variant: Math.floor(Math.random() * 20) + 1 });
              navigate(`/training/workouts/${fresh.id}`);
              return fresh;
            })}>Generate a different version</button>
            <button type="button" className="btn btn-ghost btn-danger" disabled={busy} onClick={() => act(async () => { await api.discardWorkout(w.id); navigate("/training"); })}>Discard</button>
          </div>
        </section>
      )}

      {w.status === "in_progress" && rest && restLeft > 0 && (
        <div className="rest-bar" role="status" aria-live="polite">
          Rest {clock(restLeft)}
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRest(null)}>Skip</button>
        </div>
      )}

      <ol className="exercise-list">
        {w.exercises.map((e, i) => (
          <li key={e.id} className={`card exercise-card ${e.completed ? "done" : ""}`} aria-label={e.name}>
            <div className="exercise-head">
              <span className="ex-num">{i + 1}</span>
              <div className="ex-title">
                <strong>{e.name}</strong>
                <span className="muted small">{e.role === "main" ? "Main lift" : "Accessory"} · {e.equipment.join(", ")}</span>
              </div>
              {e.completed && <span className="pill pill-ok">Done</span>}
              {w.status !== "completed" && e.sets.length === 0 && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSwap(e)}>Replace</button>
              )}
            </div>
            <div className="ex-plan small">
              <span><strong>Plan:</strong> {targetText(e)}</span>
              <span>{restText(e.rest_seconds)}</span>
              <span>~{e.est_minutes} min</span>
              {e.suggested_weight_kg != null && <span>Suggested {fromKg(e.suggested_weight_kg, unit)} {unit}</span>}
            </div>
            {e.last_summary && <div className="muted small">{e.last_summary}</div>}
            {e.replaced_exercise_id && <div className="muted small">You swapped this in for {e.replaced_exercise_id.replace(/_/g, " ")}.</div>}
            {e.notes.map((n) => <div key={n} className="small text-warn">⚠ {n}</div>)}
            {w.status === "planned" && e.instructions.length > 0 && (
              <details className="small"><summary>How to do it</summary><ol>{e.instructions.map((s) => <li key={s}>{s}</li>)}</ol></details>
            )}
            {(w.status !== "planned") && (
              <SetLog w={w} e={e} unit={unit} busy={busy}
                      onLogged={(out) => { setW(out); if (e.rest_seconds) setRest({ until: Date.now() + e.rest_seconds * 1000, total: e.rest_seconds }); }}
                      onDelete={(setId) => act(() => api.deleteSet(w.id, setId))}
                      onError={setError} />
            )}
            {w.status === "in_progress" && !e.completed && e.sets.length > 0 && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => act(() => api.markExercise(w.id, e.id, true))}>Mark exercise done</button>
            )}
          </li>
        ))}
      </ol>

      {w.status === "in_progress" && (
        <div className="finish-row">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act(async () => { const out = await api.finishWorkout(w.id); if (!navigator.userAgent.includes("jsdom")) window.scrollTo({ top: 0 }); return out; })}>Finish workout</button>
          <button type="button" className="btn btn-ghost btn-danger" disabled={busy} onClick={() => act(async () => { await api.discardWorkout(w.id); navigate("/training"); })}>Discard</button>
        </div>
      )}

      {swap && <ReplaceSheet workout={w} exercise={swap} onClose={() => setSwap(null)} onReplaced={(out) => { setSwap(null); setW(out); }} />}
    </div>
  );
}

function SetLog({ w, e, unit, busy, onLogged, onDelete, onError }: {
  w: Workout; e: WorkoutExercise; unit: "kg" | "lb"; busy: boolean;
  onLogged: (w: Workout) => void; onDelete: (setId: number) => void; onError: (m: string) => void;
}) {
  const defaults = nextSetDefaults(e, unit);
  const [weight, setWeight] = useState(defaults.weight);
  const [reps, setReps] = useState(defaults.reps);
  const [seconds, setSeconds] = useState(defaults.seconds);
  const [saving, setSaving] = useState(false);
  const bodyweight = e.equipment.length === 1 && e.equipment[0] === "body only";

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setSaving(true);
    try {
      onLogged(await api.logSet(w.id, {
        workout_exercise_id: e.id, unit,
        reps: e.measure === "reps" ? Number(reps) : null,
        duration_seconds: e.measure === "time" ? Number(seconds) : null,
        weight: weight === "" ? null : Number(weight),
      }));
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Could not log the set.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="set-log">
      {e.sets.length > 0 && (
        <table className="set-table small">
          <thead><tr><th>Set</th><th>Planned</th><th>Logged</th><th aria-label="Actions" /></tr></thead>
          <tbody>
            {e.sets.map((s) => (
              <tr key={s.id}>
                <td>{s.set_index}</td>
                <td className="muted">{e.measure === "time" ? `${e.target_seconds} s` : `${e.rep_low}–${e.rep_high}`}</td>
                <td>
                  {e.measure === "time" ? `${s.duration_seconds} s` : `${s.reps} reps`}
                  {s.weight_kg != null && ` × ${fromKg(s.weight_kg, unit)} ${unit}`}
                </td>
                <td>{w.status === "in_progress" && (
                  <button type="button" className="link-btn" aria-label={`Delete set ${s.set_index}`} onClick={() => onDelete(s.id)}>remove</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {w.status === "in_progress" && (
        <form className="set-form" onSubmit={submit} aria-label={`Log set for ${e.name}`}>
          <span className="set-label small">Set {e.sets.length + 1}</span>
          <label className="field compact"><span>{bodyweight ? `Added weight (${unit})` : `Weight (${unit})`}</span>
            <input type="number" inputMode="decimal" min="0" step="any" value={weight} onChange={(x) => setWeight(x.target.value)}
                   placeholder={bodyweight ? "0" : ""} aria-label={`Weight in ${unit}`} />
          </label>
          {e.measure === "reps" ? (
            <label className="field compact"><span>Reps</span>
              <input type="number" inputMode="numeric" min="0" max="100" value={reps} onChange={(x) => setReps(x.target.value)} required aria-label="Reps" />
            </label>
          ) : (
            <label className="field compact"><span>Seconds</span>
              <input type="number" inputMode="numeric" min="1" max="3600" value={seconds} onChange={(x) => setSeconds(x.target.value)} required aria-label="Seconds" />
            </label>
          )}
          <button className="btn btn-primary btn-sm" disabled={saving || busy}>✓ Log set</button>
        </form>
      )}
    </div>
  );
}

function SummaryCard({ w, unit }: { w: Workout; unit: "kg" | "lb" }) {
  const s = w.summary!;
  const diff = s.difference_minutes ?? 0;
  return (
    <section className="card summary-card" aria-label="Workout summary">
      <div className="summary-grid">
        <div className="stat"><span className="stat-value">{s.actual_minutes}<span className="stat-unit"> min</span></span><span className="muted small">actual</span></div>
        <div className="stat"><span className="stat-value">{s.planned_minutes}<span className="stat-unit"> min</span></span><span className="muted small">planned</span></div>
        <div className="stat"><span className={`stat-value ${diff > 5 ? "text-warn" : ""}`}>{diff > 0 ? "+" : ""}{diff}<span className="stat-unit"> min</span></span>
          <span className="muted small">{differenceText(s.difference_minutes)}</span></div>
        <div className="stat"><span className="stat-value">{s.sets_logged}<span className="stat-unit">/{s.sets_planned}</span></span><span className="muted small">sets logged</span></div>
        <div className="stat"><span className="stat-value">{Math.round(fromKg(s.volume_kg, unit) ?? 0).toLocaleString()}<span className="stat-unit"> {unit}</span></span><span className="muted small">volume (weight × reps)</span></div>
      </div>
      <p className="muted small">{formatDateTime(w.started_at)} → {formatDateTime(w.finished_at)}. Planned time is Venn's estimate when the workout was generated; actual time is from Start to Finish.</p>
      {s.records.length > 0 && (
        <div className="records"><strong>New personal bests:</strong> {s.records.map((r) => `${r.exercise} ${fromKg(r.weight_kg, unit)} ${unit} (was ${fromKg(r.previous_kg, unit)})`).join("; ")}</div>
      )}
    </section>
  );
}
