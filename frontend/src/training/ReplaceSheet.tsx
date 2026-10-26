import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Alternative, Workout, WorkoutExercise } from "../types";

/** User-initiated swap: show compatible alternatives (server-filtered) and let the user pick one. */
export default function ReplaceSheet({ workout, exercise, onClose, onReplaced }: {
  workout: Workout; exercise: WorkoutExercise; onClose: () => void; onReplaced: (w: Workout) => void;
}) {
  const [items, setItems] = useState<Alternative[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.alternatives(workout.id, exercise.id)
      .then((r) => { setItems(r.alternatives); setMessage(r.message); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load alternatives."));
  }, [workout.id, exercise.id]);

  async function choose(a: Alternative) {
    setBusy(a.id);
    setError(null);
    try {
      onReplaced(await api.replaceExercise(workout.id, exercise.id, a.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not replace the exercise.");
      setBusy(null);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="Replace exercise" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2>Replace {exercise.name}</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p className="muted small">These options train a similar movement and fit your equipment and reported limitations.
          Venn remembers your choice for future workouts.</p>
        {error && <div className="alert alert-error small" role="alert">{error}</div>}
        {items === null && !error && <p className="muted">Loading…</p>}
        {message && <div className="alert alert-info small">{message}</div>}
        <ul className="food-list" aria-label="Alternatives">
          {items?.map((a) => (
            <li key={a.id}>
              <button type="button" className="food-row alt-row" onClick={() => choose(a)} disabled={busy !== null}>
                <span className="food-row-main">
                  <span className="food-name">{a.name}</span>
                  <span className="muted small">{a.reason}</span>
                  <span className="muted small">Equipment: {a.equipment.join(", ")} · level: {a.level}</span>
                  {a.notes.map((n) => <span key={n} className="small text-warn">⚠ {n}</span>)}
                </span>
                <span className="food-row-side small">{busy === a.id ? "Replacing…" : "Choose"}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
