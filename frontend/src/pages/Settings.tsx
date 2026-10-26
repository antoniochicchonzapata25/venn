import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import LimitationsPanel from "../components/LimitationsPanel";
import ProfileForm from "../components/ProfileForm";
import TargetsPanel from "../components/TargetsPanel";
import type { Options, Profile, Target, User } from "../types";

export default function Settings({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reloadTarget = useCallback(() => api.currentTarget().then((t) => setTarget(t.target)), []);

  useEffect(() => {
    Promise.all([api.profile(), api.currentTarget(), api.options()])
      .then(([p, t, o]) => { setProfile(p); setTarget(t.target); setOptions(o); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load settings."));
  }, []);

  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>;
  if (!profile || !options) return <div className="page muted">Loading…</div>;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Profile &amp; settings</h1>
          <p className="muted">Venn uses these answers to calculate your targets and build your workouts. Unit switches only change how values are shown.</p>
        </div>
      </header>
      {!profile.is_complete && (
        <div className="alert alert-info">Welcome! Fill in the form below and press <strong>Save profile</strong> to get your targets.</div>
      )}
      <div className="settings-grid">
        <ProfileForm
          profile={profile}
          options={options}
          onSaved={(p, t) => { setProfile(p); if (t) setTarget(t); }}
        />
        <div className="stack">
          <TargetsPanel target={target} profile={profile} disclaimer={options.disclaimer} onChanged={reloadTarget} />
          <LimitationsPanel />
          <section className="card account-card">
            <h2>Account</h2>
            <p className="muted small">Signed in as <strong>{user.username}</strong>. Your data is visible only to this account.</p>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>
          </section>
        </div>
      </div>
    </div>
  );
}
