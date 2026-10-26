import { Link } from "react-router-dom";
import type { DaySummary } from "../types";
import NutrientBar from "./NutrientBar";

const ROWS = [
  { key: "kcal", name: "Calories", unit: "kcal", tone: "tone-kcal" },
  { key: "protein_g", name: "Protein", unit: "g", tone: "tone-protein" },
  { key: "carb_g", name: "Carbs", unit: "g", tone: "tone-carb" },
  { key: "fat_g", name: "Fat", unit: "g", tone: "tone-fat" },
] as const;

/** Calories and macros for one day, from persisted entries and the target in effect that day. */
export default function DaySummaryCard({ day, compact = false }: { day: DaySummary; compact?: boolean }) {
  const kcal = day.progress.kcal;
  return (
    <section className="card day-summary" aria-label="Daily nutrition summary">
      {!compact && (
        <div className="kcal-hero">
          <div>
            <span className="kcal-big">{Math.round(kcal.consumed).toLocaleString()}</span>
            <span className="muted"> kcal eaten</span>
          </div>
          {kcal.target != null ? (
            <div className="kcal-side">
              {kcal.state === "over" ? (
                <><span className="kcal-big text-warn">{Math.round(kcal.over ?? 0).toLocaleString()}</span><span className="muted"> over</span></>
              ) : (
                <><span className="kcal-big">{Math.round(kcal.remaining ?? 0).toLocaleString()}</span><span className="muted"> remaining</span></>
              )}
            </div>
          ) : null}
        </div>
      )}
      <div className="nbars">
        {ROWS.map((r) => (
          <NutrientBar key={r.key} name={r.name} unit={r.unit} tone={r.tone}
                       consumed={day.totals[r.key]} target={day.target ? day.target[r.key] : null}
                       range={r.key === "protein_g" ? day.protein_range ?? null : null} />
        ))}
      </div>
      {!day.target && (
        <p className="alert alert-info small no-target-note">
          No nutrition target is set for this date, so Venn shows what you ate without a goal.{" "}
          <Link to="/settings">Set up targets in Settings</Link>.
        </p>
      )}
    </section>
  );
}
