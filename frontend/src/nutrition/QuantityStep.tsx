import { type FormEvent, useMemo, useState } from "react";
import { api, ApiError, confirmationFrom } from "../api";
import type { ConfirmationNeeded, FoodDetail, FoodEntry } from "../types";
import ConfirmBox from "./ConfirmBox";
import { previewNutrition, round1 } from "./logic";

/** Pick quantity, unit and time for one food, preview the nutrition, and save. */
export default function QuantityStep({ food, initialQuantity, initialUnit, eatenAt, onSaved, onBack }: {
  food: FoodDetail;
  initialQuantity?: number;
  initialUnit?: string;
  eatenAt: string;
  onSaved: (e: FoodEntry) => void;
  onBack: () => void;
}) {
  const startUnit = food.units.find((u) => u.unit === initialUnit) ?? food.units[0];
  const [quantity, setQuantity] = useState(String(initialQuantity ?? (startUnit.kind === "count" ? 1 : 100)));
  const [unit, setUnit] = useState(startUnit.unit);
  const [time, setTime] = useState(eatenAt);
  const [errors, setErrors] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<ConfirmationNeeded | null>(null);
  const [busy, setBusy] = useState(false);

  const unitOption = food.units.find((u) => u.unit === unit);
  const preview = useMemo(() => previewNutrition(food.per_100, Number(quantity), unitOption), [food, quantity, unitOption]);

  async function save(q: number, u: string, confirmed: boolean) {
    setBusy(true);
    setErrors([]);
    try {
      const entry = await api.addEntry({ food_id: food.id, quantity: q, unit: u, eaten_at: time, confirm: confirmed });
      onSaved(entry);
    } catch (err) {
      const c = confirmationFrom(err);
      if (c) setConfirm(c);
      else setErrors(err instanceof ApiError ? err.details : ["Could not save. Please try again."]);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setConfirm(null);
    save(Number(quantity), unit, false);
  }

  return (
    <form className="stack" onSubmit={submit} aria-label="Quantity">
      <div className="food-head">
        <button type="button" className="btn btn-ghost btn-sm" onClick={onBack} aria-label="Back to food list">‹ Back</button>
        <div>
          <div className="food-name">{food.name}</div>
          <div className="muted small">{[food.brand, food.source_label].filter(Boolean).join(" · ")}</div>
        </div>
      </div>
      <div className="row qty-row">
        <label className="field"><span>Quantity</span>
          <input id="qty" type="number" inputMode="decimal" step="any" min="0" value={quantity} autoFocus
                 onChange={(e) => { setQuantity(e.target.value); setConfirm(null); }} required />
        </label>
        <label className="field"><span>Unit</span>
          <select id="unit" value={unit} onChange={(e) => { setUnit(e.target.value); setConfirm(null); }}>
            {food.units.map((u) => <option key={u.unit} value={u.unit}>{u.label}</option>)}
          </select>
        </label>
      </div>
      <label className="field"><span>Date and time eaten</span>
        <input id="eaten_at" type="datetime-local" value={time} onChange={(e) => setTime(e.target.value)} required />
      </label>

      <div className="preview" aria-live="polite" data-testid="preview">
        {preview ? (
          <>
            <span className="preview-kcal">{Math.round(preview.kcal).toLocaleString()} kcal</span>
            <span>P {round1(preview.protein_g)} g</span>
            <span>C {round1(preview.carb_g)} g</span>
            <span>F {round1(preview.fat_g)} g</span>
          </>
        ) : <span className="muted">Enter a quantity above zero.</span>}
      </div>
      <p className="muted small source-note">
        {food.per_100.kcal} kcal per 100 {food.basis}. Source: {food.source_label}{food.source_ref ? ` (FDC ${food.source_ref})` : ""}.
      </p>

      {confirm && (
        <ConfirmBox c={confirm} busy={busy}
                    onSuggestion={(s) => { setQuantity(String(s.quantity)); setUnit(s.unit); setConfirm(null); save(s.quantity, s.unit, false); }}
                    onConfirm={() => save(Number(quantity), unit, true)} />
      )}
      {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
      <button className="btn btn-primary" disabled={busy || !preview}>{busy ? "Saving…" : "Add to log"}</button>
    </form>
  );
}
