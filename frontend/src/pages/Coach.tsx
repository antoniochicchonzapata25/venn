import { type FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { localDate } from "../nutrition/logic";
import type { CoachMetrics, CoachRun, CoachStatus } from "../types";

const EXAMPLES = [
  "How am I doing against my protein goal?",
  "Which days did I fall outside my protein range?",
  "What's a good alternative to barbell squats for me?",
  "I've trained consistently this week, but I'm struggling to hit my protein goal. What could I change?",
];
const WORKFLOW_NAMES: Record<string, string> = { nutrition: "Nutrition Agent", training: "Training Agent", progress: "Progress Coach" };

const usd = (n: number) => (n === 0 ? "$0" : n < 0.01 ? `$${n.toFixed(6)}` : `$${n.toFixed(4)}`);

function RunCard({ run, onTrace }: { run: CoachRun; onTrace?: () => void }) {
  const c = run.checks ?? {};
  return (
    <section className="card stack" aria-label="Coach answer">
      <div className="card-head">
        <h2>{WORKFLOW_NAMES[run.workflow] ?? "Coach"}</h2>
        <span className="pill" title="How the question was routed">routed by {run.routed_by}</span>
      </div>
      <p className="muted small">Q: {run.question}</p>
      {run.status === "ok" ? (
        <>
          <p className="muted small">AI answer from {run.model}, based on the tool results below:</p>
          <p className="answer-text" data-testid="coach-answer">{run.answer}</p>
        </>
      ) : (
        <div className="alert alert-error" role="alert">{run.error}</div>
      )}
      <div className="check-row" role="group" aria-label="Checks">
        {c.grounded === true && <span className="pill pill-ok">✓ {c.numbers_verified} number{c.numbers_verified === 1 ? "" : "s"} match your records</span>}
        {c.grounded === false && <span className="pill pill-bad">⚠ Not found in your records: {c.unverified_numbers?.join(", ")}</span>}
        {(c.exercise_conflicts ?? []).map((x) => (
          <span key={x.exercise} className="pill pill-bad">⚠ {x.exercise} conflicts with your profile: {x.reasons.join("; ")}</span>
        ))}
        {(c.untrusted_text_flags ?? []).map((f) => <span key={f} className="pill pill-warn">🛡 {f}</span>)}
      </div>
      <p className="muted small">
        Tools: {run.tools_used.length ? run.tools_used.join(", ") : "none"} · {run.model_calls} model call{run.model_calls === 1 ? "" : "s"} ·{" "}
        {run.usage.complete ? `${run.usage.input_tokens.toLocaleString()} input (${run.usage.cached_input_tokens.toLocaleString()} cached) + ${run.usage.output_tokens.toLocaleString()} output tokens`
          : "token usage not reported by the provider"} · est. {usd(run.estimated_cost_usd)} · {(run.latency_ms / 1000).toFixed(1)} s
      </p>
      {onTrace && <button type="button" className="btn btn-ghost btn-sm" onClick={onTrace}>Show run trace</button>}
      {run.trace && <Trace run={run} />}
      <p className="disclaimer small">General fitness and nutrition information, not medical advice. Numbers come from Venn's own calculations; the AI explains them.</p>
    </section>
  );
}

function Trace({ run }: { run: CoachRun }) {
  return (
    <details className="small" open>
      <summary>Run trace #{run.id}</summary>
      <table className="trace-table">
        <thead><tr><th>#</th><th>Step</th><th>Details</th></tr></thead>
        <tbody>
          {(run.trace ?? []).map((s, i) => {
            const { step, ...rest } = s as { step: string };
            return (<tr key={i}><td>{i + 1}</td><td>{step}</td><td><code>{JSON.stringify(rest)}</code></td></tr>);
          })}
        </tbody>
      </table>
      <p className="muted">Costs use {run.price_source}. Token counts are as reported by the API.</p>
    </details>
  );
}

export default function Coach() {
  const [status, setStatus] = useState<CoachStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [workflow, setWorkflow] = useState("auto");
  const [current, setCurrent] = useState<CoachRun | null>(null);
  const [runs, setRuns] = useState<CoachRun[]>([]);
  const [metrics, setMetrics] = useState<CoachMetrics | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    api.coachStatus().then(setStatus).catch(() => undefined);
    api.coachRuns().then((r) => setRuns(r.runs)).catch(() => undefined);
    api.coachMetrics(localDate()).then(setMetrics).catch(() => undefined);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const r = await api.coachAsk(question, workflow, localDate());
      if ("id" in r) setCurrent(r as CoachRun);
      else setMessage(r.message);
      refresh();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "The coach could not answer right now.");
    } finally {
      setBusy(false);
    }
  }

  const enabled = status?.enabled ?? false;
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>AI Coach</h1>
          <p className="muted">Ask about your nutrition, training or progress. Answers use your real records through read-only tools.</p>
        </div>
        {status && <span className={`pill ${enabled ? "pill-ok" : "pill-muted"}`}>{enabled ? `${status.model} · ${status.runs_today}/${status.daily_limit} today` : "AI unavailable"}</span>}
      </header>
      {status && !enabled && <div className="alert alert-info" role="status">{status.message}</div>}

      <div className="coach-grid">
        <div className="stack">
          <form className="card stack coach-form" onSubmit={submit} aria-label="Ask the coach">
            <label className="field"><span>Your question</span>
              <textarea id="coach_q" maxLength={500} value={question} onChange={(e) => setQuestion(e.target.value)} disabled={!enabled} required />
            </label>
            <div className="examples">
              {EXAMPLES.map((q) => <button key={q} type="button" className="chip" disabled={!enabled} onClick={() => setQuestion(q)}>{q}</button>)}
            </div>
            <div className="btn-row">
              <select id="coach_workflow" value={workflow} onChange={(e) => setWorkflow(e.target.value)} aria-label="Agent" disabled={!enabled}>
                <option value="auto">Automatic routing</option>
                <option value="nutrition">Nutrition Agent</option>
                <option value="training">Training Agent</option>
                <option value="progress">Progress Coach</option>
              </select>
              <button className="btn btn-primary" disabled={!enabled || busy || question.trim().length < 3}>{busy ? "Thinking…" : "Ask"}</button>
            </div>
          </form>
          {message && <div className="alert alert-warn" role="alert">{message}</div>}
          {current && <RunCard run={current} />}
        </div>

        <div className="stack">
          <section className="card" aria-label="Your numbers">
            <h2>Your numbers (last 7 days)</h2>
            <p className="muted small">Calculated by Venn from your records, not by AI. The Progress Coach receives these same numbers.</p>
            {metrics ? (
              <dl className="metric-list">
                <dt>Days with food logged</dt><dd>{metrics.nutrition.days_logged}</dd>
                <dt>Avg protein (logged days)</dt><dd>{metrics.nutrition.average_protein_g_on_logged_days ?? "-"} g</dd>
                <dt>Days within protein range</dt><dd>{metrics.nutrition.days_within_protein_range}</dd>
                <dt>Days below protein range</dt><dd>{metrics.nutrition.days_below_protein_range}</dd>
                <dt>Workouts completed</dt><dd>{metrics.training.completed_workouts}{metrics.training.of_which_demo_data ? ` (${metrics.training.of_which_demo_data} demo)` : ""}</dd>
                <dt>Avg minutes vs. plan</dt><dd>{metrics.training.average_minutes_over_plan ?? "-"}</dd>
                <dt>Body measurements</dt><dd>{metrics.body_measurements}</dd>
              </dl>
            ) : <p className="muted">Loading…</p>}
          </section>
          <section className="card" aria-label="Recent questions">
            <h2>Recent questions</h2>
            {runs.length === 0 ? <p className="muted">No questions yet.</p> : (
              <ul className="run-list">
                {runs.map((r) => (
                  <li key={r.id}>
                    <button type="button" onClick={() => api.coachRun(r.id).then(setCurrent)}>
                      <span className="small"><strong>{WORKFLOW_NAMES[r.workflow] ?? r.workflow}</strong> · {r.status}</span>
                      <span className="muted small">{r.question}</span>
                      <span className="muted small">{r.usage.input_tokens + r.usage.output_tokens} tokens · est. {usd(r.estimated_cost_usd)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
