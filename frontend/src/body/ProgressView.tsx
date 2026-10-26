import { type FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { localDate } from "../nutrition/logic";
import type { MeasurementField, MeasurementHistory, WeightEntry, WeightHistory } from "../types";
import { type LengthUnit, MEASUREMENT_LABELS, cmIn, fieldChange, kgIn, shortDate, signed } from "./logic";

const FIELDS: MeasurementField[] = ["waist", "chest", "hips", "biceps", "thigh"];

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.details.join(" ") : fallback;
}

/** Small line chart of weight over time (oldest -> newest). Points are spaced by date. */
function WeightChart({ entries, unit }: { entries: WeightEntry[]; unit: "kg" | "lb" }) {
  const pts = [...entries].reverse();
  if (pts.length < 2) return null;
  const W = 520, H = 170, L = 44, R = 12, T = 12, B = 26;
  const t = pts.map((p) => new Date(`${p.entry_date}T00:00:00`).getTime());
  const v = pts.map((p) => kgIn(p.weight_kg, unit));
  const t0 = Math.min(...t), t1 = Math.max(...t);
  let lo = Math.min(...v), hi = Math.max(...v);
  if (hi - lo < 1) { lo -= 0.5; hi += 0.5; }
  const x = (ms: number) => L + (t1 === t0 ? 0.5 : (ms - t0) / (t1 - t0)) * (W - L - R);
  const y = (val: number) => T + (1 - (val - lo) / (hi - lo)) * (H - T - B);
  const line = pts.map((_, i) => `${i ? "L" : "M"}${x(t[i]).toFixed(1)},${y(v[i]).toFixed(1)}`).join(" ");
  return (
    <svg className="weight-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Weight chart: ${pts.length} entries from ${shortDate(pts[0].entry_date)} to ${shortDate(pts[pts.length - 1].entry_date)}`}>
      <line x1={L} x2={W - R} y1={y(hi)} y2={y(hi)} className="grid-line" />
      <line x1={L} x2={W - R} y1={y(lo)} y2={y(lo)} className="grid-line" />
      <text x={L - 6} y={y(hi) + 4} textAnchor="end">{hi.toFixed(1)}</text>
      <text x={L - 6} y={y(lo) + 4} textAnchor="end">{lo.toFixed(1)}</text>
      <text x={L} y={H - 6}>{shortDate(pts[0].entry_date)}</text>
      <text x={W - R} y={H - 6} textAnchor="end">{shortDate(pts[pts.length - 1].entry_date)}</text>
      <path d={line} className="chart-line" />
      {pts.map((p, i) => <circle key={p.id} cx={x(t[i])} cy={y(v[i])} r={3.5} className="chart-dot"><title>{`${shortDate(p.entry_date)}: ${v[i]} ${unit}`}</title></circle>)}
    </svg>
  );
}

export default function ProgressView({ weightUnit, lengthUnit }: { weightUnit: "kg" | "lb"; lengthUnit: LengthUnit }) {
  const [weights, setWeights] = useState<WeightHistory | null>(null);
  const [measures, setMeasures] = useState<MeasurementHistory | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [wDate, setWDate] = useState(localDate());
  const [wValue, setWValue] = useState("");
  const [wMsg, setWMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const [mDate, setMDate] = useState(localDate());
  const [mValues, setMValues] = useState<Record<MeasurementField, string>>({ waist: "", chest: "", hips: "", biceps: "", thigh: "" });
  const [mMsg, setMMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [baseId, setBaseId] = useState<string>("auto");

  useEffect(() => {
    api.bodyWeights().then(setWeights).catch(() => setLoadError("Could not load your weight history."));
    api.bodyMeasurements().then(setMeasures).catch(() => setLoadError("Could not load your measurements."));
  }, []);

  async function saveWeight(e: FormEvent) {
    e.preventDefault();
    setWMsg(null);
    const n = Number(wValue);
    if (wValue.trim() === "" || !Number.isFinite(n) || n <= 0) { setWMsg({ kind: "error", text: "Enter your weight as a positive number." }); return; }
    try {
      const r = await api.addWeight({ entry_date: wDate, weight: n, unit: weightUnit });
      setWeights(r);
      setWValue("");
      setWMsg({ kind: "ok", text: r.replaced ? `Updated your weight for ${shortDate(wDate)}.` : `Saved ${n} ${weightUnit} for ${shortDate(wDate)}.` });
    } catch (err) {
      setWMsg({ kind: "error", text: errorText(err, "Could not save the weight.") });
    }
  }

  async function removeWeight(id: number) {
    await api.deleteWeight(id);
    setWeights(await api.bodyWeights());
  }

  async function saveMeasurement(e: FormEvent) {
    e.preventDefault();
    setMMsg(null);
    const body: Record<string, number> = {};
    for (const f of FIELDS) {
      const text = mValues[f].trim();
      if (!text) continue;
      const n = Number(text);
      if (!Number.isFinite(n) || n <= 0) { setMMsg({ kind: "error", text: `${MEASUREMENT_LABELS[f]}: enter a positive number.` }); return; }
      body[f] = n;
    }
    if (!Object.keys(body).length) { setMMsg({ kind: "error", text: "Enter at least one measurement." }); return; }
    try {
      const r = await api.addMeasurement({ entry_date: mDate, unit: lengthUnit, ...body });
      setMeasures(r);
      setMValues({ waist: "", chest: "", hips: "", biceps: "", thigh: "" });
      setMMsg({ kind: "ok", text: r.replaced ? `Replaced your measurements for ${shortDate(mDate)}.` : `Saved measurements for ${shortDate(mDate)}.` });
    } catch (err) {
      setMMsg({ kind: "error", text: errorText(err, "Could not save the measurements.") });
    }
  }

  async function removeMeasurement(id: number) {
    await api.deleteMeasurement(id);
    setMeasures(await api.bodyMeasurements());
    setBaseId("auto");
  }

  const latestM = measures?.entries[0];
  const baseEntry = baseId === "auto" ? undefined : measures?.entries.find((m) => String(m.id) === baseId);

  return (
    <div className="body-progress">
      {loadError && <div className="alert alert-error">{loadError}</div>}

      <section className="card stack" aria-label="Body weight">
        <div className="card-head"><h2>Body weight</h2><span className="muted small">Shown in {weightUnit}</span></div>
        <div className="stat-row">
          <div className="stat"><span className="muted small">Latest</span>
            <strong>{weights?.latest ? `${kgIn(weights.latest.weight_kg, weightUnit)} ${weightUnit}` : "-"}</strong>
            <span className="muted small">{weights?.latest ? shortDate(weights.latest.entry_date) : "No entries yet"}</span></div>
          <div className="stat"><span className="muted small">Previous</span>
            <strong>{weights?.previous ? `${kgIn(weights.previous.weight_kg, weightUnit)} ${weightUnit}` : "-"}</strong>
            <span className="muted small">{weights?.previous ? shortDate(weights.previous.entry_date) : "Need two entries"}</span></div>
          <div className="stat"><span className="muted small">Difference</span>
            <strong data-testid="weight-change">{weights?.change_kg != null ? signed(kgIn(weights.change_kg, weightUnit), weightUnit) : "-"}</strong>
            <span className="muted small">{weights?.days_between != null ? `over ${weights.days_between} day${weights.days_between === 1 ? "" : "s"}` : ""}</span></div>
        </div>
        {weights && weights.entries.length >= 2 && <WeightChart entries={weights.entries} unit={weightUnit} />}
        <form className="inline-form" onSubmit={saveWeight} noValidate>
          <label className="field"><span>Date</span>
            <input id="weight_date" type="date" value={wDate} max={localDate()} onChange={(e) => setWDate(e.target.value)} required /></label>
          <label className="field"><span>Weight ({weightUnit})</span>
            <input id="weight_value" type="number" inputMode="decimal" step="0.1" min="0" value={wValue} onChange={(e) => setWValue(e.target.value)} required /></label>
          <button className="btn btn-primary">Save weight</button>
        </form>
        {wMsg && <p className={`alert alert-${wMsg.kind === "ok" ? "ok" : "error"}`} role={wMsg.kind === "error" ? "alert" : "status"}>{wMsg.text}</p>}
        {weights && weights.entries.length > 0 && (
          <details>
            <summary>History ({weights.entries.length} {weights.entries.length === 1 ? "entry" : "entries"})</summary>
            <ul className="entry-list">
              {weights.entries.map((w) => (
                <li key={w.id}><span>{shortDate(w.entry_date)}</span><strong>{kgIn(w.weight_kg, weightUnit)} {weightUnit}</strong>
                  <button className="btn btn-ghost btn-sm btn-danger" onClick={() => removeWeight(w.id)} aria-label={`Delete weight for ${shortDate(w.entry_date)}`}>Delete</button></li>
              ))}
            </ul>
          </details>
        )}
        {weights && weights.entries.length === 0 && <p className="muted small">No weight recorded yet. Add your first entry above.</p>}
      </section>

      <section className="card stack" aria-label="Body measurements">
        <div className="card-head"><h2>Measurements</h2><span className="muted small">Shown in {lengthUnit}</span></div>
        {measures && measures.entries.length > 0 ? (
          <>
            <label className="field compare-select"><span>Compare latest ({latestM ? shortDate(latestM.entry_date) : "-"}) with</span>
              <select id="compare_base" value={baseId} onChange={(e) => setBaseId(e.target.value)}>
                <option value="auto">Previous recorded value for each measurement</option>
                {measures.entries.slice(1).map((m) => <option key={m.id} value={m.id}>{shortDate(m.entry_date)}</option>)}
              </select>
            </label>
            <table className="compare-table">
              <thead><tr><th>Measurement</th><th>Latest</th><th>Compared with</th><th>Change</th></tr></thead>
              <tbody>
                {FIELDS.map((f) => {
                  const c = measures.comparison[f];
                  if (baseId === "auto") {
                    return (
                      <tr key={f}><th scope="row">{MEASUREMENT_LABELS[f]}</th>
                        <td>{c.latest_cm != null ? `${cmIn(c.latest_cm, lengthUnit)} ${lengthUnit}` : <span className="muted">not recorded</span>}
                          {c.latest_date && <div className="muted small">{shortDate(c.latest_date)}</div>}</td>
                        <td>{c.previous_cm != null ? `${cmIn(c.previous_cm, lengthUnit)} ${lengthUnit}` : <span className="muted">-</span>}
                          {c.previous_date && <div className="muted small">{shortDate(c.previous_date)}</div>}</td>
                        <td>{c.change_cm != null ? signed(cmIn(c.change_cm, lengthUnit), lengthUnit) : "-"}</td></tr>
                    );
                  }
                  const a = latestM?.[`${f}_cm`];
                  const b = baseEntry?.[`${f}_cm`];
                  return (
                    <tr key={f}><th scope="row">{MEASUREMENT_LABELS[f]}</th>
                      <td>{a != null ? `${cmIn(a, lengthUnit)} ${lengthUnit}` : <span className="muted">not recorded</span>}</td>
                      <td>{b != null ? `${cmIn(b, lengthUnit)} ${lengthUnit}` : <span className="muted">not recorded</span>}</td>
                      <td>{signed(fieldChange(latestM, baseEntry, f, lengthUnit), lengthUnit)}</td></tr>
                  );
                })}
              </tbody>
            </table>
          </>
        ) : measures && <p className="muted small">No measurements yet. Record any of waist, chest, hips, biceps or thigh below; leave the rest blank.</p>}
        <form className="stack" onSubmit={saveMeasurement} noValidate>
          <div className="measure-grid">
            <label className="field"><span>Date</span>
              <input id="measure_date" type="date" value={mDate} max={localDate()} onChange={(e) => setMDate(e.target.value)} required /></label>
            {FIELDS.map((f) => (
              <label className="field" key={f}><span>{MEASUREMENT_LABELS[f]} ({lengthUnit})</span>
                <input id={`measure_${f}`} type="number" inputMode="decimal" step="0.1" min="0" value={mValues[f]}
                  onChange={(e) => setMValues({ ...mValues, [f]: e.target.value })} /></label>
            ))}
          </div>
          <div className="btn-row"><button className="btn btn-primary">Save measurements</button>
            <span className="muted small">Saving again for the same date replaces that day's entry.</span></div>
        </form>
        {mMsg && <p className={`alert alert-${mMsg.kind === "ok" ? "ok" : "error"}`} role={mMsg.kind === "error" ? "alert" : "status"}>{mMsg.text}</p>}
        {measures && measures.entries.length > 0 && (
          <details>
            <summary>History ({measures.entries.length} {measures.entries.length === 1 ? "entry" : "entries"})</summary>
            <ul className="entry-list">
              {measures.entries.map((m) => (
                <li key={m.id}><span>{shortDate(m.entry_date)}</span>
                  <span className="small">{FIELDS.filter((f) => m[`${f}_cm`] != null).map((f) => `${MEASUREMENT_LABELS[f]} ${cmIn(m[`${f}_cm`]!, lengthUnit)}`).join(" · ")} {lengthUnit}</span>
                  <button className="btn btn-ghost btn-sm btn-danger" onClick={() => removeMeasurement(m.id)} aria-label={`Delete measurements for ${shortDate(m.entry_date)}`}>Delete</button></li>
              ))}
            </ul>
          </details>
        )}
      </section>
      <p className="disclaimer small">{weights?.note ?? "Recorded values only."} Logging weight here does not change your targets; update your weight in Settings to recalculate them.</p>
    </div>
  );
}
