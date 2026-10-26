import { useState } from "react";
import { api, ApiError } from "../api";
import type { AiCheck, Health } from "../types";

export default function AiStatusCard({ health }: { health: Health | null }) {
  const [check, setCheck] = useState<AiCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const configured = health?.ai.configured ?? false;

  async function runCheck() {
    setBusy(true);
    setError(null);
    try {
      setCheck(await api.checkAi());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not run the check.");
    } finally {
      setBusy(false);
    }
  }

  const state = check?.status ?? (configured ? "unknown" : "disabled");
  const badge = {
    ok: ["Connected", "pill-ok"], error: ["Unreachable", "pill-warn"],
    disabled: ["Disabled", "pill-muted"], unknown: ["Not checked", "pill-muted"],
  }[state] as [string, string];

  return (
    <section className="card">
      <div className="card-head">
        <h2>AI Coach</h2>
        <span className={`pill ${badge[1]}`} data-testid="ai-badge">{badge[0]}</span>
      </div>
      {!configured ? (
        <p className="muted">
          AI features are disabled because no <code>PORTKEY_API_KEY</code> was found. Everything else in Venn works normally.
        </p>
      ) : (
        <>
          <p className="muted small">Model: <code>{health?.ai.model}</code></p>
          {check?.status === "ok" && check.usage && (
            <p className="small">
              Replied in {check.latency_ms} ms using {check.usage.input_tokens} input
              ({check.usage.cached_input_tokens} cached) and {check.usage.output_tokens} output tokens
              {check.cached ? " (result from the last 10 minutes)" : ""}.
            </p>
          )}
          {check?.status === "error" && <p className="alert alert-warn small">{check.message}</p>}
          {error && <p className="alert alert-error small">{error}</p>}
          <button type="button" className="btn btn-ghost btn-sm" onClick={runCheck} disabled={busy}>
            {busy ? "Checking…" : "Test connection"}
          </button>
        </>
      )}
    </section>
  );
}
