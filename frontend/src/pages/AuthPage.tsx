import { type FormEvent, useState } from "react";
import { api, ApiError } from "../api";
import { APP_NAME, APP_TAGLINE } from "../brand";
import Logo from "../components/Logo";
import type { User } from "../types";

export default function AuthPage({ onAuthenticated }: { onAuthenticated: (u: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErrors([]);
    setBusy(true);
    try {
      const user = mode === "login"
        ? await api.login(username, password)
        : await api.register(username, password, displayName);
      onAuthenticated(user);
    } catch (err) {
      setErrors(err instanceof ApiError ? err.details : ["Could not reach Venn. Is the server running?"]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <Logo size={64} />
        <h1>{APP_NAME}</h1>
        <p className="lead">{APP_TAGLINE}</p>
        <ul className="hero-points">
          <li>Targets built from transparent formulas, with safety minimums</li>
          <li>Workouts that fit your equipment, time and reported limitations</li>
          <li>Insights that connect what you eat, how you train, and how you progress</li>
        </ul>
      </section>

      <section className="card auth-card">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "tab active" : "tab"}
                  onClick={() => { setMode("login"); setErrors([]); }}>Log in</button>
          <button role="tab" aria-selected={mode === "register"} className={mode === "register" ? "tab active" : "tab"}
                  onClick={() => { setMode("register"); setErrors([]); }}>Create account</button>
        </div>
        <form onSubmit={submit} className="stack">
          <label className="field">
            <span>Username</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username"
                   required minLength={3} maxLength={32} />
          </label>
          {mode === "register" && (
            <label className="field">
              <span>Display name <em className="muted">(optional)</em></span>
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={60} />
            </label>
          )}
          <label className="field">
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   autoComplete={mode === "login" ? "current-password" : "new-password"} required
                   minLength={mode === "register" ? 8 : 1} />
            {mode === "register" && <small className="muted">At least 8 characters.</small>}
          </label>
          {errors.length > 0 && (
            <div className="alert alert-error" role="alert">{errors.map((e) => <div key={e}>{e}</div>)}</div>
          )}
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
        <p className="muted small demo-hint">
          Trying it out? Log in as <code>demo</code> with password <code>venn-demo-2026</code>.
        </p>
      </section>
    </div>
  );
}
