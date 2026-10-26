import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import AddFoodSheet from "../nutrition/AddFoodSheet";
import DaySummaryCard from "../nutrition/DaySummaryCard";
import EditEntrySheet from "../nutrition/EditEntrySheet";
import { defaultEatenAt, formatTime, friendlyDate, localDate, quantityText, shiftDate } from "../nutrition/logic";
import type { DaySummary, FoodEntry } from "../types";

export default function Nutrition() {
  const [params, setParams] = useSearchParams();
  const today = localDate();
  const day = params.get("date") && /^\d{4}-\d{2}-\d{2}$/.test(params.get("date")!) ? params.get("date")! : today;
  const [summary, setSummary] = useState<DaySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<FoodEntry | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    return api.day(day).then(setSummary).catch((e) => setError(e instanceof ApiError ? e.message : "Could not load your log."));
  }, [day]);

  useEffect(() => { load(); }, [load]);

  const goTo = (d: string) => setParams(d === today ? {} : { date: d });

  function saved(e: FoodEntry) {
    setAdding(false);
    setFlash(`Added ${e.description.split(",")[0]} · ${Math.round(e.kcal)} kcal`);
    if (e.local_date !== day) goTo(e.local_date); else load();
    setTimeout(() => setFlash(null), 3500);
  }

  return (
    <div className="page nutrition-page">
      <header className="page-head">
        <div>
          <h1>Nutrition</h1>
          <p className="muted">Your food log, in the order you ate it.</p>
        </div>
        <div className="day-nav" aria-label="Choose day">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => goTo(shiftDate(day, -1))} aria-label="Previous day">‹</button>
          <label className="day-pick">
            <span className="day-label">{friendlyDate(day, today)}</span>
            <input type="date" value={day} max="2100-12-31" onChange={(e) => e.target.value && goTo(e.target.value)} aria-label="Date" />
          </label>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => goTo(shiftDate(day, 1))} aria-label="Next day">›</button>
          {day !== today && <button type="button" className="btn btn-ghost btn-sm" onClick={() => goTo(today)}>Today</button>}
          <button type="button" className="btn btn-primary desktop-add" onClick={() => setAdding(true)}>+ Add food</button>
        </div>
      </header>

      {flash && <div className="alert alert-ok" role="status">{flash}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {summary && (
        <div className="nutrition-grid">
          <DaySummaryCard day={summary} />
          <section className="card" aria-label="Food log">
            <div className="card-head">
              <h2>Food log</h2>
              <span className="muted small">{summary.entries.length} {summary.entries.length === 1 ? "entry" : "entries"}</span>
            </div>
            {summary.entries.length === 0 ? (
              <div className="empty-state">
                <p>Nothing logged for {friendlyDate(day, today).toLowerCase()} yet.</p>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => setAdding(true)}>Log your first food</button>
              </div>
            ) : (
              <ol className="log-list">
                {summary.entries.map((e) => (
                  <li key={e.id}>
                    <button type="button" className="log-row" onClick={() => setEditing(e)} aria-label={`Edit ${e.description} at ${formatTime(e.eaten_at)}`}>
                      <time className="log-time" dateTime={e.eaten_at}>{formatTime(e.eaten_at)}</time>
                      <span className="log-main">
                        <span className="log-name">{e.description}</span>
                        <span className="muted small">{quantityText(e.quantity, e.unit_label, e.unit)}{e.brand ? ` · ${e.brand}` : ""}{e.kind === "manual" ? " · manual" : ""}</span>
                      </span>
                      <span className="log-nums">
                        <strong>{Math.round(e.kcal)}</strong> <span className="muted small">kcal</span>
                        <span className="muted small macro-line">P {e.protein_g} · C {e.carb_g} · F {e.fat_g}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}

      <button type="button" className="fab" onClick={() => setAdding(true)} aria-label="Add food">+</button>

      {adding && <AddFoodSheet eatenAt={defaultEatenAt(day)} onClose={() => setAdding(false)} onSaved={saved} />}
      {editing && <EditEntrySheet entry={editing} onClose={() => setEditing(null)} onChanged={() => { setEditing(null); load(); }} />}
    </div>
  );
}
