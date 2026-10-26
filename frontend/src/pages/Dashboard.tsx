import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import AiStatusCard from "../components/AiStatusCard";
import { label } from "../labels";
import DaySummaryCard from "../nutrition/DaySummaryCard";
import { localDate } from "../nutrition/logic";
import type { DaySummary, Health, Limitation, Profile, TrainingSummary, User, WeekSummary } from "../types";

export default function Dashboard({ user }: { user: User }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [today, setToday] = useState<DaySummary | null>(null);
  const [week, setWeek] = useState<WeekSummary | null>(null);
  const [training, setTraining] = useState<TrainingSummary | null>(null);
  const [limitations, setLimitations] = useState<Limitation[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const date = localDate();
    Promise.all([api.profile(), api.day(date), api.week(date), api.limitations(), api.health()])
      .then(([p, d, w, l, h]) => { setProfile(p); setToday(d); setWeek(w); setLimitations(l); setHealth(h); })
      .then(() => api.trainingSummary().then(setTraining).catch(() => undefined))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load your dashboard."));
  }, []);

  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>;
  if (!profile || !today) return <div className="page muted">Loading…</div>;

  const active = limitations.filter((l) => l.active);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Hi, {user.display_name}</h1>
          <p className="muted">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
        </div>
      </header>

      {!profile.is_complete && (
        <section className="card callout">
          <h2>Set up your plan</h2>
          <p>Answer a few quick questions about your goals, schedule and equipment. It takes about two minutes, and every
            number Venn calculates is shown with its formula.</p>
          <Link to="/welcome" className="btn btn-primary">Complete your profile</Link>
        </section>
      )}

      <div className="grid">
        <div className="span-2 today-card">
          <div className="card-head">
            <h2>Today</h2>
            <Link to="/nutrition" className="btn btn-primary btn-sm">Open food log</Link>
          </div>
          <DaySummaryCard day={today} />
          <p className="muted small">{today.entries.length} {today.entries.length === 1 ? "food" : "foods"} logged today.</p>
        </div>

        <section className="card">
          <h2>This week</h2>
          <div className="stat-row">
            <div className="stat"><span className="stat-value">{week?.days_logged ?? 0}<span className="stat-unit">/7</span></span><span className="muted small">days with food logged</span></div>
            <div className="stat"><span className="stat-value">{training?.completed_last_7_days ?? 0}<span className="stat-unit">/{profile.days_per_week ?? "-"}</span></span><span className="muted small">workouts done</span></div>
          </div>
          {week && (
            <div className="week-dots" aria-label="Food logged in the last 7 days">
              {week.days.map((d) => (
                <span key={d.date} className={d.entries ? "dot on" : "dot"} title={`${d.date}: ${d.entries} entries, ${Math.round(d.kcal)} kcal`}>
                  {new Date(d.date + "T12:00").toLocaleDateString(undefined, { weekday: "narrow" })}
                </span>
              ))}
            </div>
          )}
          {training?.average_difference_minutes != null && (
            <p className="muted small">Workouts ran {training.average_difference_minutes > 0 ? "+" : ""}{training.average_difference_minutes} min vs. plan on average (last {training.sessions_compared}).</p>
          )}
        </section>

        <section className="card">
          <h2>Training setup</h2>
          {profile.is_complete ? (
            <dl className="facts">
              <dt>Goal</dt><dd>{label("training_goal", profile.training_goal)}</dd>
              <dt>Schedule</dt><dd>{profile.days_per_week} days × {profile.session_minutes} min</dd>
              <dt>Split</dt><dd>{label("preferred_split", profile.preferred_split)}</dd>
              <dt>Equipment</dt><dd>{profile.equipment?.length ? profile.equipment.join(", ") : "Body weight only"}</dd>
            </dl>
          ) : <p className="muted">Not set yet.</p>}
          <Link to="/training" className="btn btn-primary btn-sm">{training?.planned ? `Start ${training.planned.name}` : "Generate a workout"}</Link>
        </section>

        <section className="card">
          <h2>Reported limitations</h2>
          {active.length ? (
            <ul className="plain-list">
              {active.map((l) => (
                <li key={l.id}><strong>{label("body_area", l.body_area)}</strong> · {label("severity", l.severity)}</li>
              ))}
            </ul>
          ) : <p className="muted">None reported.</p>}
          <Link to="/settings#limitations" className="link small">Manage limitations</Link>
        </section>

        <AiStatusCard health={health} />
      </div>
    </div>
  );
}
