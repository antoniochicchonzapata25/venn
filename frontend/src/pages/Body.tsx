import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import ProgressView from "../body/ProgressView";
import RecoveryView from "../body/RecoveryView";
import type { Profile } from "../types";

type View = "progress" | "recovery";

/** Body: self-recorded weight and measurements (Progress) and a workout-history recovery estimate (Recovery). */
export default function Body() {
  const [params, setParams] = useSearchParams();
  const view: View = params.get("view") === "recovery" ? "recovery" : "progress";
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState(false);

  // Wait for the profile so values are never typed in one unit and sent in another (falls back to metric).
  useEffect(() => { api.profile().then(setProfile).catch(() => undefined).finally(() => setReady(true)); }, []);

  const weightUnit = profile?.weight_unit ?? (profile?.units === "imperial" ? "lb" : "kg");
  const lengthUnit = profile?.height_unit === "ft_in" ? "in" : "cm";
  const select = (v: View) => setParams(v === "progress" ? {} : { view: v }, { replace: true });

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Body</h1>
          <p className="muted">Track your weight and measurements, and see which muscle groups your recent workouts loaded.</p>
        </div>
        <div className="segmented" role="tablist" aria-label="Body view">
          {(["progress", "recovery"] as View[]).map((v) => (
            <button key={v} role="tab" id={`tab-${v}`} aria-selected={view === v} aria-controls={`panel-${v}`}
              className={view === v ? "on" : ""} onClick={() => select(v)}>
              {v === "progress" ? "Progress" : "Recovery"}
            </button>
          ))}
        </div>
      </header>
      <div role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
        {view === "recovery" ? <RecoveryView /> : ready ? <ProgressView weightUnit={weightUnit} lengthUnit={lengthUnit} /> : <p className="muted">Loading…</p>}
      </div>
    </div>
  );
}
