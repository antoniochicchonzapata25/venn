import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { differenceText, formatDateTime } from "../training/logic";
import type { TrainingOptions, TrainingSummary } from "../types";

/** Training home: resume or review the current workout, generate a new one, see history. */
export default function Training() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<TrainingSummary | null>(null);
  const [options, setOptions] = useState<TrainingOptions | null>(null);
  const [dayType, setDayType] = useState<string>("");
  const [split, setSplit] = useState<string>("");
  const autoTried = useRef(false);
  const [minutes, setMinutes] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState<{ message: string; alternatives: string[] } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.trainingSummary().then(setSummary).catch(() => setError("Could not load training."));
    api.trainingOptions()
      .then((o) => { setOptions(o); setMinutes(String(o.session_minutes)); setSplit(o.preferred_split ?? "auto"); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load training options."));
  }, []);

  // Have the next workout ready: if nothing is planned or in progress, generate it automatically (deterministic, no AI).
  useEffect(() => {
    if (!summary || !options || autoTried.current || summary.planned || summary.in_progress) return;
    autoTried.current = true;
    api.generateWorkout({}).then(() => api.trainingSummary().then(setSummary)).catch(() => undefined);
  }, [summary, options]);

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setProblem(null);
    setError(null);
    try {
      const w = await api.generateWorkout({ day_type: dayType || null, minutes: Number(minutes),
        split: split && split !== options?.preferred_split ? split : undefined });
      navigate(`/training/workouts/${w.id}`);
    } catch (err) {
      const detail = err instanceof ApiError ? (err.body as { detail?: { message?: string; alternatives?: string[] } })?.detail : null;
      if (detail && typeof detail === "object" && "message" in detail && detail.message) {
        setProblem({ message: detail.message, alternatives: detail.alternatives ?? [] });
      } else {
        setError(err instanceof ApiError ? err.message : "Could not generate a workout.");
      }
    } finally {
      setBusy(false);
    }
  }

  const nextName = options?.all_day_types.find((d) => d.id === options.next_day_type)?.name;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Training</h1>
          <p className="muted">Workouts built around your goal, equipment, time and reported limitations.</p>
        </div>
        {summary && (
          <div className="week-pill" aria-label="Workouts this week">
            <strong>{summary.completed_last_7_days}</strong>/{summary.days_per_week ?? "-"} workouts in the last 7 days
          </div>
        )}
      </header>

      {error && (
        <div className="alert alert-error">{error} {error.includes("profile") && <Link to="/settings">Open Settings</Link>}</div>
      )}

      {summary?.in_progress && (
        <section className="card callout" aria-label="Workout in progress">
          <h2>{summary.in_progress.name} in progress</h2>
          <p>Started {formatDateTime(summary.in_progress.started_at)}.</p>
          <Link className="btn btn-primary" to={`/training/workouts/${summary.in_progress.id}`}>Resume workout</Link>
        </section>
      )}

      <div className="training-grid">
        <section className="card stack" aria-label="Generate workout">
          <h2>{summary?.planned ? "Ready to train" : "New workout"}</h2>
          {summary?.planned && (
            <div className="planned-box">
              <div>
                <strong>{summary.planned.name}</strong>
                <div className="muted small">About {summary.planned.planned_minutes} min · generated {formatDateTime(summary.planned.created_at)}</div>
              </div>
              <Link className="btn btn-primary btn-sm" to={`/training/workouts/${summary.planned.id}`}>Review &amp; start</Link>
            </div>
          )}
          {options && (
            <form className="stack" onSubmit={generate}>
              <p className="muted small">Venn uses {options.split_reason}. Next up: <strong>{nextName}</strong>.</p>
              <label className="field"><span>Training split</span>
                <select id="split" value={split} onChange={(e) => { setSplit(e.target.value); setDayType(""); }}>
                  {options.splits.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                {split !== options.preferred_split && <small className="muted">Generating will save this as your default split.</small>}
              </label>
              <div className="row">
                <label className="field"><span>Workout</span>
                  <select id="day_type" value={dayType} onChange={(e) => setDayType(e.target.value)}>
                    <option value="">Next in my plan ({nextName})</option>
                    {options.all_day_types.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                  </select>
                </label>
                <label className="field"><span>Time available (min)</span>
                  <input id="minutes" type="number" min={15} max={180} step={5} value={minutes} onChange={(e) => setMinutes(e.target.value)} required />
                </label>
              </div>
              {problem && (
                <div className="alert alert-warn" role="alert">
                  <strong>{problem.message}</strong>
                  <ul>{problem.alternatives.map((a) => <li key={a}>{a}</li>)}</ul>
                </div>
              )}
              <button className="btn btn-primary" disabled={busy}>
                {busy ? "Building…" : summary?.planned ? "Generate a new workout" : "Generate workout"}
              </button>
              <p className="muted small">Exercises from a curated public-domain catalog. Venn never guesses limitations:
                it only uses the ones you reported in <Link to="/settings#limitations">Settings</Link>.</p>
            </form>
          )}
        </section>

        <section className="card" aria-label="Workout history">
          <div className="card-head">
            <h2>History</h2>
            {summary?.average_difference_minutes != null && (
              <span className="pill" title={`Average over your last ${summary.sessions_compared} sessions`}>
                Avg {differenceText(Math.round(summary.average_difference_minutes))}
              </span>
            )}
          </div>
          {!summary || summary.history.length === 0 ? (
            <p className="muted">No completed workouts yet.</p>
          ) : (
            <ol className="history-list">
              {summary.history.map((w) => (
                <li key={w.id}>
                  <Link className="history-row" to={`/training/workouts/${w.id}`}>
                    <span>
                      <strong>{w.name}</strong>{w.is_demo && <span className="pill pill-muted demo-pill">Demo data</span>}
                      <span className="muted small block">{formatDateTime(w.finished_at)}</span>
                    </span>
                    <span className="history-nums small">
                      <span>{w.summary?.actual_minutes} min <span className="muted">/ {w.planned_minutes} planned</span></span>
                      <span className={(w.summary?.difference_minutes ?? 0) > 5 ? "text-warn" : "muted"}>
                        {differenceText(w.summary?.difference_minutes ?? null)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
