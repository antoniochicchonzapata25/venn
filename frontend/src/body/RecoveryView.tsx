import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { formatDateTime } from "../training/logic";
import type { MuscleGroupId, Recovery, RecoveryState } from "../types";
import BodyFigure from "./BodyFigure";
import { STATE_COLORS, STATE_SHORT, daysSinceText, shortDate } from "./logic";

const LEGEND: { state: RecoveryState; text: string }[] = [
  { state: "none", text: "Grey: not assessed (no logged sets in the last 7 days, or no data)" },
  { state: "low", text: "Light red: low estimated residual fatigue" },
  { state: "moderate", text: "Medium red: moderate estimated residual fatigue" },
  { state: "high", text: "Dark red: high estimated residual fatigue" },
];

export default function RecoveryView() {
  const [data, setData] = useState<Recovery | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MuscleGroupId | null>(null);
  const [rating, setRating] = useState("");
  const [sorenessMsg, setSorenessMsg] = useState<string | null>(null);

  useEffect(() => {
    api.recovery().then(setData).catch(() => setError("Could not load the recovery estimate."));
  }, []);

  useEffect(() => {
    const r = selected ? data?.soreness[selected]?.rating : undefined;
    setRating(r == null ? "" : String(r));
    setSorenessMsg(null);
  }, [selected, data]);

  if (error) return <div className="alert alert-error">{error}</div>;
  if (!data) return <p className="muted">Loading recovery…</p>;

  const g = selected ? data.groups.find((x) => x.id === selected) : undefined;
  const sore = selected ? data.soreness[selected] : undefined;

  async function saveRating() {
    if (!selected) return;
    const n = Number(rating);
    if (rating === "" || !Number.isInteger(n) || n < 0 || n > 10) { setSorenessMsg("Choose a whole number from 0 to 10."); return; }
    try {
      const r = await api.setSoreness(selected, n);
      setData({ ...data!, soreness: { ...data!.soreness, [selected]: { rating: r.rating, recorded_at: r.recorded_at } } });
      setSorenessMsg("Saved.");
    } catch (e) {
      setSorenessMsg(e instanceof ApiError ? e.message : "Could not save the rating.");
    }
  }

  async function clearRating() {
    if (!selected) return;
    await api.deleteSoreness(selected);
    const next = { ...data!.soreness };
    delete next[selected];
    setData({ ...data!, soreness: next });
  }

  return (
    <div className="stack">
      {!data.has_history && (
        <div className="alert alert-info" role="status">
          No completed workouts yet, so there is nothing to estimate: every muscle group shows as not assessed.
          Finish a workout in <Link to="/training">Training</Link> and log your sets to see an estimate.
        </div>
      )}
      <div className="recovery-layout">
        <aside className="card recovery-side" aria-label="Last workout">
          <h2>Last workout</h2>
          {data.last_workout ? (
            <dl className="indicator-list">
              <div><dt>Days since</dt><dd data-testid="days-since">{daysSinceText(data.last_workout.days_since)}</dd></div>
              <div><dt>Date</dt><dd>{shortDate(data.last_workout.local_date)}</dd></div>
              <div><dt>Muscle groups trained</dt><dd>{data.last_workout.groups_trained} of 10</dd></div>
              <div><dt>Workout</dt><dd>{data.last_workout.name}{data.last_workout.is_demo && <span className="pill pill-muted"> Demo data</span>}</dd></div>
            </dl>
          ) : <p className="muted small">No completed workout recorded.</p>}
        </aside>

        <section className="card recovery-center" aria-label="Muscle recovery map">
          <BodyFigure groups={data.groups} selected={selected} onSelect={setSelected} />
          <ul className="legend" aria-label="Legend">
            {LEGEND.map((l) => (
              <li key={l.state}><span className={`swatch swatch-${l.state}`} style={{ background: STATE_COLORS[l.state] }} aria-hidden="true" />{l.text}</li>
            ))}
          </ul>
          <p className="muted small center">Select a muscle group for details.</p>
        </section>

        <aside className="card recovery-side" aria-label="Fatigue summary">
          <h2>Muscle groups</h2>
          <dl className="indicator-list">
            <div><dt><span className="swatch" style={{ background: STATE_COLORS.low }} aria-hidden="true" /> Fresh / low fatigue</dt><dd data-testid="count-low">{data.counts.low}</dd></div>
            <div><dt><span className="swatch" style={{ background: STATE_COLORS.moderate }} aria-hidden="true" /> Moderate fatigue</dt><dd data-testid="count-moderate">{data.counts.moderate}</dd></div>
            <div><dt><span className="swatch" style={{ background: STATE_COLORS.high }} aria-hidden="true" /> High fatigue</dt><dd data-testid="count-high">{data.counts.high}</dd></div>
            <div><dt><span className="swatch swatch-none" style={{ background: STATE_COLORS.none }} aria-hidden="true" /> Not assessed</dt><dd data-testid="count-none">{data.counts.none}</dd></div>
          </dl>
          <p className="muted small">Counts cover the 10 groups and always add up to 10. "Fresh / low" means logged in the last {data.model.window_days} days with little estimated load left; "Not assessed" means no logged sets in that window.</p>
        </aside>
      </div>

      {g && (
        <section className="card stack muscle-detail" aria-label={`${g.label} details`}>
          <div className="card-head">
            <h2>{g.label}</h2>
            <span className={`pill state-pill state-${g.state}`}>{STATE_SHORT[g.state]}</span>
          </div>
          {g.last_workout ? (
            <>
              <p className="small">Most recent logged workout involving it: <strong>{g.last_workout.name}</strong>, {formatDateTime(g.last_workout.finished_at)}
                {g.last_workout.is_demo && <span className="pill pill-muted"> Demo data</span>}</p>
              <ul className="small">
                {g.exercises.map((e) => (
                  <li key={e.name}>{e.name}: {e.sets} logged set{e.sets === 1 ? "" : "s"} ({e.role} muscle, counted as {e.weighted_sets} weighted set{e.weighted_sets === 1 ? "" : "s"})</li>
                ))}
              </ul>
              <p className="small">Last {data.model.window_days} days: {g.weighted_sets_7d} weighted sets. Estimated remaining load: <strong>{g.residual}</strong> (moderate from {data.model.moderate_at}, high from {data.model.high_at}).</p>
            </>
          ) : <p className="small muted">No logged sets for this muscle group in your completed workouts.</p>}
          <p className="small muted">{data.model.explanation}</p>

          <div className="soreness-box">
            <h3>Your soreness (user-reported)</h3>
            <p className="small muted">Optional. Your own 0–10 rating, kept separate from the estimate above and never used to change it.</p>
            {sore && <p className="small">Recorded: <strong>{sore.rating}/10</strong> on {formatDateTime(sore.recorded_at)}</p>}
            <div className="btn-row">
              <label className="field soreness-field"><span>Rating (0–10)</span>
                <input id="soreness_rating" type="number" min={0} max={10} step={1} value={rating} onChange={(e) => setRating(e.target.value)} /></label>
              <button className="btn btn-ghost btn-sm" onClick={saveRating}>{sore ? "Update rating" : "Save rating"}</button>
              {sore && <button className="btn btn-ghost btn-sm btn-danger" onClick={clearRating}>Delete rating</button>}
            </div>
            {sorenessMsg && <p className="small" role="status">{sorenessMsg}</p>}
          </div>
        </section>
      )}
      <p className="disclaimer small">{data.model.disclaimer}</p>
    </div>
  );
}
