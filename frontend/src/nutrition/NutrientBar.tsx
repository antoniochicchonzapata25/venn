import type { ProteinRange } from "../types";
import { barSegments, fmt, rangeMessage } from "./logic";

const STATUS: Record<string, string> = {
  empty: "Nothing logged yet",
  met: "Target reached",
};

/** One horizontal progress bar: filled = eaten, light shade = remaining, hatched = over target. */
export default function NutrientBar({ name, unit, consumed, target, tone, range = null }: {
  name: string; unit: "kcal" | "g"; consumed: number; target: number | null; tone: string; range?: ProteinRange | null;
}) {
  const s = barSegments(consumed, target);
  let detail: string;
  if (s.state === "no_target") detail = "No target set";
  else if (s.state === "over") detail = `${fmt(consumed - (target ?? 0), unit)} over`;
  else if (s.state === "met") detail = STATUS.met;
  else detail = `${fmt(Math.max((target ?? 0) - consumed, 0), unit)} left`;

  return (
    <div className={`nbar nbar-${s.state}`} data-testid={`bar-${name.toLowerCase()}`}>
      <div className="nbar-head">
        <span className="nbar-name">{name}</span>
        <span className="nbar-values">
          <strong>{fmt(consumed, unit)}</strong>
          {target != null && <span className="muted"> / {fmt(target, unit)}</span>}
        </span>
      </div>
      {s.state !== "no_target" && (
        <div className="nbar-track" role="progressbar" aria-label={`${name}: ${fmt(consumed, unit)} of ${fmt(target ?? 0, unit)}`}
             aria-valuemin={0} aria-valuemax={target ?? 0} aria-valuenow={Math.round(consumed)}>
          <div className={`nbar-fill ${tone}`} style={{ width: `${s.filled}%` }} />
          {s.remaining > 0 && <div className="nbar-remaining" style={{ width: `${s.remaining}%` }} />}
          {s.over > 0 && <div className="nbar-over" style={{ width: `${s.over}%` }} />}
        </div>
      )}
      {range ? (
        <div className={`nbar-detail small ${range.state === "within" ? "text-ok" : "muted"}`} data-testid="protein-range">
          <strong>Goal: {range.low}–{range.high} g</strong> · {rangeMessage(range)}
        </div>
      ) : (
        <div className={`nbar-detail small ${s.state === "over" ? "text-warn" : "muted"}`}>
          {s.state === "empty" && target != null ? `${STATUS.empty} · ${fmt(target, unit)} left` : detail}
        </div>
      )}
    </div>
  );
}
