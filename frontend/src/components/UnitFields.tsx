import { useEffect, useState } from "react";
import { cmToFtIn, ftInToCm, type HeightUnit, parseWeight, weightText, type WeightUnit } from "../units";

/** A small segmented control for switching display units beside a field. */
export function UnitSwitch<T extends string>({ value, options, onChange, label }: {
  value: T; options: { id: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <span className="unit-switch" role="group" aria-label={`${label} unit`}>
      {options.map((o) => (
        <button key={o.id} type="button" className={o.id === value ? "on" : ""} aria-pressed={o.id === value}
                onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </span>
  );
}

/**
 * Weight input in kg or lb. The parent stores kg at full precision; switching units only changes
 * the text shown, so values never drift when switching back and forth.
 */
export function WeightField({ id, label, kg, unit, onKg, onUnit, required, hint }: {
  id: string; label: string; kg: number | null; unit: WeightUnit; onKg: (kg: number | null) => void;
  onUnit: (u: WeightUnit) => void; required?: boolean; hint?: string;
}) {
  const [text, setText] = useState(weightText(kg, unit));
  useEffect(() => { setText(weightText(kg, unit)); }, [unit]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // external change (e.g. a reset): resync unless the text already represents this value
    if (parseWeight(text, unit) !== kg && !(kg == null && text === "")) setText(weightText(kg, unit));
  }, [kg]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="field">
      <span className="field-label-row">
        <label htmlFor={id}>{label}</label>
        <UnitSwitch label={label} value={unit} onChange={onUnit} options={[{ id: "kg", label: "kg" }, { id: "lb", label: "lb" }]} />
      </span>
      <input id={id} type="number" inputMode="decimal" step="0.1" min="0" value={text} required={required}
             onChange={(e) => { setText(e.target.value); onKg(parseWeight(e.target.value, unit)); }} />
      {hint && <small className="muted">{hint}</small>}
    </div>
  );
}

/** Height in cm, or feet + inches. Stored as cm at full precision. */
export function HeightField({ id, cm, unit, onCm, onUnit, label = "Height" }: {
  id: string; cm: number | null; unit: HeightUnit; onCm: (cm: number | null) => void; onUnit: (u: HeightUnit) => void; label?: string;
}) {
  const split = cm != null ? cmToFtIn(cm) : null;
  const [cmText, setCmText] = useState(cm != null ? String(Math.round(cm * 10) / 10) : "");
  const [ftText, setFtText] = useState(split ? String(split.ft) : "");
  const [inText, setInText] = useState(split ? String(split.inches) : "");
  useEffect(() => {
    const s = cm != null ? cmToFtIn(cm) : null;
    setCmText(cm != null ? String(Math.round(cm * 10) / 10) : "");
    setFtText(s ? String(s.ft) : "");
    setInText(s ? String(s.inches) : "");
  }, [unit]); // eslint-disable-line react-hooks/exhaustive-deps

  function fromFtIn(ft: string, inch: string) {
    if (ft === "" && inch === "") return onCm(null);
    onCm(ftInToCm(Number(ft || 0), Number(inch || 0)));
  }

  return (
    <div className="field">
      <span className="field-label-row">
        <label htmlFor={unit === "cm" ? id : `${id}_ft`}>{label}</label>
        <UnitSwitch label={label} value={unit} onChange={onUnit} options={[{ id: "cm", label: "cm" }, { id: "ft_in", label: "ft/in" }]} />
      </span>
      {unit === "cm" ? (
        <input id={id} type="number" inputMode="decimal" step="0.1" min="0" value={cmText} required
               onChange={(e) => { setCmText(e.target.value); onCm(e.target.value === "" ? null : Number(e.target.value)); }} />
      ) : (
        <span className="ft-in">
          <input id={`${id}_ft`} type="number" inputMode="numeric" min="3" max="8" value={ftText} required aria-label="Feet"
                 onChange={(e) => { setFtText(e.target.value); fromFtIn(e.target.value, inText); }} />
          <span className="muted">ft</span>
          <input id={`${id}_in`} type="number" inputMode="decimal" step="0.5" min="0" max="11.9" value={inText} aria-label="Inches"
                 onChange={(e) => { setInText(e.target.value); fromFtIn(ftText, e.target.value); }} />
          <span className="muted">in</span>
        </span>
      )}
    </div>
  );
}
