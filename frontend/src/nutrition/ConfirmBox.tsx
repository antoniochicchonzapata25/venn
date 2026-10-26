import type { ConfirmationNeeded } from "../types";

/** Shown when the server flags an entry as unusual. The user fixes it or saves it anyway. */
export default function ConfirmBox({ c, onSuggestion, onConfirm, busy }: {
  c: ConfirmationNeeded;
  onSuggestion: (s: { quantity: number; unit: string }) => void;
  onConfirm: () => void;
  busy?: boolean;
}) {
  return (
    <div className="alert alert-warn confirm-box" role="alert">
      <strong>Please check this entry</strong>
      <ul>{c.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      <div className="small">As entered: {Math.round(c.preview.kcal).toLocaleString()} kcal.</div>
      <div className="btn-row">
        {c.suggestions.map((s) => (
          <button type="button" key={s.label} className="btn btn-primary btn-sm" onClick={() => onSuggestion(s)}>{s.label}</button>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" onClick={onConfirm} disabled={busy}>It's correct, save anyway</button>
      </div>
    </div>
  );
}
