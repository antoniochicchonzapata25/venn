import { type FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { LABELS, label } from "../labels";
import type { Limitation } from "../types";

type Draft = Omit<Limitation, "id" | "created_at" | "updated_at">;
const EMPTY: Draft = { body_area: "", kind: "temporary", severity: "caution", note: "", active: true };

export default function LimitationsPanel() {
  const [items, setItems] = useState<Limitation[]>([]);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [adding, setAdding] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const load = () => api.limitations().then(setItems).catch(() => setErrors(["Could not load limitations."]));
  useEffect(() => { load(); }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setErrors([]);
    try {
      await api.addLimitation(draft);
      setDraft(EMPTY);
      setAdding(false);
      await load();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not save."]);
    }
  }

  async function toggleActive(l: Limitation) {
    const { id, created_at: _c, updated_at: _u, ...rest } = l;
    await api.updateLimitation(id, { ...rest, active: !l.active });
    await load();
  }

  async function remove(l: Limitation) {
    if (!window.confirm(`Delete the ${label("body_area", l.body_area).toLowerCase()} limitation?`)) return;
    await api.deleteLimitation(l.id);
    await load();
  }

  return (
    <section className="card stack" id="limitations" aria-label="Limitations">
      <div className="card-head">
        <h2>Injuries &amp; limitations</h2>
      </div>
      <p className="muted small">
        Report areas you want Venn to avoid or treat with caution when it builds workouts. Venn only uses what you
        report here: it does not diagnose injuries, guess at limitations, or decide what is medically safe.
      </p>

      {items.length === 0 && <p className="muted">Nothing reported.</p>}
      <ul className="limitation-list">
        {items.map((l) => (
          <li key={l.id} className={l.active ? "" : "inactive"}>
            <div>
              <strong>{label("body_area", l.body_area)}</strong>{" "}
              <span className="pill pill-muted">{label("kind", l.kind)}</span>{" "}
              <span className={l.severity === "avoid" ? "pill pill-warn" : "pill"}>{label("severity", l.severity)}</span>
              {!l.active && <span className="pill pill-muted">Resolved</span>}
              {l.note && <div className="muted small">{l.note}</div>}
            </div>
            <div className="btn-row">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleActive(l)}>
                {l.active ? "Mark resolved" : "Reactivate"}
              </button>
              <button type="button" className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(l)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>

      {adding ? (
        <form onSubmit={add} className="stack" aria-label="Add limitation">
          <div className="row">
            <label className="field"><span>Body area</span>
              <select id="body_area" value={draft.body_area} required onChange={(e) => setDraft({ ...draft, body_area: e.target.value })}>
                <option value="">Choose…</option>
                {Object.keys(LABELS.body_area).map((k) => <option key={k} value={k}>{label("body_area", k)}</option>)}
              </select>
            </label>
            <label className="field"><span>Type</span>
              <select id="kind" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as Draft["kind"] })}>
                <option value="temporary">Temporary</option>
                <option value="ongoing">Ongoing</option>
              </select>
            </label>
          </div>
          <label className="field"><span>How should Venn treat it?</span>
            <select id="severity" value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value as Draft["severity"] })}>
              <option value="caution">{label("severity", "caution")}</option>
              <option value="avoid">{label("severity", "avoid")}</option>
            </select>
          </label>
          <label className="field"><span>Note <em className="muted">(optional, 280 characters)</em></span>
            <textarea id="note" maxLength={280} rows={2} value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
          </label>
          {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
          <div className="btn-row">
            <button className="btn btn-primary">Save limitation</button>
            <button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>+ Report a limitation</button>
      )}
    </section>
  );
}
