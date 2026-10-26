import { type FormEvent, useState } from "react";
import { api, ApiError, confirmationFrom } from "../api";
import type { ConfirmationNeeded, FoodEntry } from "../types";
import ConfirmBox from "./ConfirmBox";

/** Edit quantity, unit or time of a logged entry, or delete it. Nutrition is recomputed by the server. */
export default function EditEntrySheet({ entry, onClose, onChanged }: {
  entry: FoodEntry; onClose: () => void; onChanged: () => void;
}) {
  const [quantity, setQuantity] = useState(String(entry.quantity));
  const [unit, setUnit] = useState(entry.unit);
  const [time, setTime] = useState(entry.eaten_at);
  const [errors, setErrors] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<ConfirmationNeeded | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save(q: number, u: string, confirmed: boolean) {
    setBusy(true);
    setErrors([]);
    try {
      await api.editEntry(entry.id, { quantity: q, unit: u, eaten_at: time, confirm: confirmed });
      onChanged();
    } catch (err) {
      const c = confirmationFrom(err);
      if (c) setConfirm(c);
      else setErrors(err instanceof ApiError ? err.details : ["Could not save."]);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteEntry(entry.id);
      onChanged();
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not delete."]);
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setConfirm(null);
    save(Number(quantity), unit, false);
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="Edit entry" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2>Edit entry</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <form className="stack" onSubmit={submit}>
          <div>
            <div className="food-name">{entry.description}</div>
            <div className="muted small">{[entry.brand, entry.source_label].filter(Boolean).join(" · ")}</div>
          </div>
          <div className="row">
            <label className="field"><span>{entry.kind === "manual" ? "Servings" : "Quantity"}</span>
              <input id="edit_qty" type="number" inputMode="decimal" step="any" min="0" value={quantity}
                     onChange={(e) => { setQuantity(e.target.value); setConfirm(null); }} required />
            </label>
            <label className="field"><span>Unit</span>
              <select id="edit_unit" value={unit} onChange={(e) => { setUnit(e.target.value); setConfirm(null); }}
                      disabled={entry.units.length < 2}>
                {entry.units.map((u) => <option key={u.unit} value={u.unit}>{u.label}</option>)}
              </select>
            </label>
          </div>
          <label className="field"><span>Date and time eaten</span>
            <input id="edit_time" type="datetime-local" value={time} onChange={(e) => setTime(e.target.value)} required />
          </label>
          <p className="muted small">
            Currently {Math.round(entry.kcal)} kcal · P {entry.protein_g} g · C {entry.carb_g} g · F {entry.fat_g} g.
            Changes are recalculated from the values this entry was logged with.
          </p>
          {confirm && (
            <ConfirmBox c={confirm} busy={busy}
                        onSuggestion={(s) => { setQuantity(String(s.quantity)); setUnit(s.unit); save(s.quantity, s.unit, false); }}
                        onConfirm={() => save(Number(quantity), unit, true)} />
          )}
          {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
          <div className="btn-row spread">
            <button className="btn btn-primary" disabled={busy}>Save changes</button>
            {armedDelete ? (
              <button type="button" className="btn btn-danger-solid" onClick={remove} disabled={busy}>Confirm delete</button>
            ) : (
              <button type="button" className="btn btn-ghost btn-danger" onClick={() => setArmedDelete(true)}>Delete entry</button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
