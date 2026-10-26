import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiError, confirmationFrom } from "../api";
import type { ConfirmationNeeded, FoodDetail, FoodEntry, FoodSummary, RecentFood } from "../types";
import { cameraAvailable, decodeImageFile, startCameraScan, type CameraScan } from "./barcodeScan";
import ConfirmBox from "./ConfirmBox";
import { quantityText } from "./logic";
import QuantityStep from "./QuantityStep";

type Tab = "recent" | "search" | "barcode" | "manual";
const TABS: { id: Tab; label: string }[] = [
  { id: "recent", label: "Recent" }, { id: "search", label: "Search" },
  { id: "barcode", label: "Barcode" }, { id: "manual", label: "Manual" },
];

interface Picked { food: FoodDetail; quantity?: number; unit?: string }

/** The add-food flow: pick (recent / search / barcode / manual) → quantity → saved. */
export default function AddFoodSheet({ eatenAt, onClose, onSaved }: {
  eatenAt: string; onClose: () => void; onSaved: (e: FoodEntry) => void;
}) {
  const [tab, setTab] = useState<Tab>("recent");
  const [picked, setPicked] = useState<Picked | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function pick(food: FoodSummary, quantity?: number, unit?: string) {
    setLoadingId(food.id);
    setError(null);
    try {
      setPicked({ food: await api.food(food.id), quantity, unit });
    } catch {
      setError("Could not load that food. Please try again.");
    } finally {
      setLoadingId(null);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="Add food" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <h2>Add food</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {picked ? (
          <QuantityStep food={picked.food} initialQuantity={picked.quantity} initialUnit={picked.unit}
                        eatenAt={eatenAt} onSaved={onSaved} onBack={() => setPicked(null)} />
        ) : (
          <>
            <div className="tabs tabs-4" role="tablist">
              {TABS.map((t) => (
                <button key={t.id} role="tab" type="button" aria-selected={tab === t.id}
                        className={tab === t.id ? "tab active" : "tab"} onClick={() => setTab(t.id)}>{t.label}</button>
              ))}
            </div>
            {error && <div className="alert alert-error small">{error}</div>}
            {tab === "recent" && <RecentTab onPick={pick} loadingId={loadingId} onEmpty={() => setTab("search")} />}
            {tab === "search" && <SearchTab onPick={(f) => pick(f)} loadingId={loadingId} />}
            {tab === "barcode" && <BarcodeTab onFound={(food) => setPicked({ food })}
                                              onSearch={() => setTab("search")} onManual={() => setTab("manual")} />}
            {tab === "manual" && <ManualTab eatenAt={eatenAt} onSaved={onSaved} />}
          </>
        )}
      </div>
    </div>
  );
}

function FoodRow({ food, line, onClick, busy }: { food: FoodSummary; line: string; onClick: () => void; busy: boolean }) {
  return (
    <li>
      <button type="button" className="food-row" onClick={onClick} disabled={busy}>
        <span className="food-row-main">
          <span className="food-name">{food.name}</span>
          <span className="muted small">{food.brand || food.category}</span>
        </span>
        <span className="food-row-side small">{line}</span>
      </button>
    </li>
  );
}

function RecentTab({ onPick, loadingId, onEmpty }: {
  onPick: (f: FoodSummary, q?: number, u?: string) => void; loadingId: number | null; onEmpty: () => void;
}) {
  const [items, setItems] = useState<RecentFood[] | null>(null);
  useEffect(() => { api.recentFoods().then((r) => setItems(r.results)).catch(() => setItems([])); }, []);
  if (items === null) return <p className="muted">Loading…</p>;
  if (items.length === 0) {
    return (
      <div className="empty-state">
        <p>Foods you log will appear here for quick re-use.</p>
        <button type="button" className="btn btn-primary btn-sm" onClick={onEmpty}>Search foods</button>
      </div>
    );
  }
  return (
    <ul className="food-list" aria-label="Recently used foods">
      {items.map((f) => (
        <FoodRow key={f.id} food={f} busy={loadingId === f.id}
                 line={`Last: ${quantityText(f.last.quantity, f.last.unit_label, f.last.unit)} · ${Math.round(f.last.kcal)} kcal`}
                 onClick={() => onPick(f, f.last.quantity, f.last.unit)} />
      ))}
    </ul>
  );
}

function SearchTab({ onPick, loadingId }: { onPick: (f: FoodSummary) => void; loadingId: number | null }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FoodSummary[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) { setResults(null); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api.searchFoods(query);
        if (!cancelled) setResults(r.results);
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [q]);

  return (
    <div className="stack">
      <label className="field"><span className="sr-only">Search foods</span>
        <input type="search" placeholder="Search foods, e.g. chicken breast, oats, banana" value={q}
               onChange={(e) => setQ(e.target.value)} autoFocus aria-label="Search foods" />
      </label>
      {busy && <p className="muted small">Searching…</p>}
      {results && results.length === 0 && !busy && (
        <p className="muted">No foods match “{q}”. Try fewer or different words, or use Manual entry.</p>
      )}
      {results && results.length > 0 && (
        <ul className="food-list" aria-label="Search results">
          {results.map((f) => (
            <FoodRow key={f.id} food={f} busy={loadingId === f.id} onClick={() => onPick(f)}
                     line={`${Math.round(f.per_100.kcal)} kcal / 100 ${f.basis}`} />
          ))}
        </ul>
      )}
      {!results && <p className="muted small">Offline USDA database: 7,793 generic foods and 20 packaged products.</p>}
    </div>
  );
}

function BarcodeTab({ onFound, onSearch, onManual }: {
  onFound: (f: FoodDetail) => void; onSearch: () => void; onManual: () => void;
}) {
  const [code, setCode] = useState("");
  const [result, setResult] = useState<FoodDetail | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [samples, setSamples] = useState<{ barcode: string; name: string; brand: string }[]>([]);
  const video = useRef<HTMLVideoElement>(null);
  const scan = useRef<CameraScan | null>(null);

  useEffect(() => { api.sampleBarcodes().then((r) => setSamples(r.products)).catch(() => undefined); }, []);
  useEffect(() => () => scan.current?.stop(), []);

  async function lookup(raw: string) {
    setResult(null); setNotFound(null); setError(null);
    try {
      setResult(await api.barcode(raw));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(raw);
      else setError(err instanceof ApiError ? err.message : "Lookup failed.");
    }
  }

  async function fromPhoto(file: File | undefined) {
    if (!file) return;
    setError(null); setResult(null); setNotFound(null);
    const decoded = await decodeImageFile(file);
    if (!decoded) { setError("No barcode was found in that photo. Try a sharper, closer photo or type the number."); return; }
    setCode(decoded);
    lookup(decoded);
  }

  async function startCamera() {
    setError(null);
    setScanning(true);
    try {
      await new Promise((r) => setTimeout(r, 0));
      scan.current = await startCameraScan(video.current!, (decoded) => {
        setScanning(false);
        setCode(decoded);
        lookup(decoded);
      });
    } catch {
      setScanning(false);
      setError("Could not start the camera (permission denied or no camera). Type the barcode or use a photo instead.");
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (code.trim()) lookup(code.trim());
  }

  return (
    <div className="stack">
      <form onSubmit={submit} className="barcode-form" aria-label="Barcode lookup">
        <label className="field"><span>Barcode number (UPC / EAN)</span>
          <input id="barcode" inputMode="numeric" autoComplete="off" placeholder="e.g. 044000065713" value={code}
                 onChange={(e) => setCode(e.target.value)} />
        </label>
        <button className="btn btn-primary">Look up</button>
      </form>
      <div className="btn-row">
        {cameraAvailable() && !scanning && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={startCamera}>Scan with camera</button>
        )}
        {scanning && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { scan.current?.stop(); setScanning(false); }}>Stop camera</button>
        )}
        <label className="btn btn-ghost btn-sm file-btn">
          Scan from photo
          <input type="file" accept="image/*" capture="environment" aria-label="Barcode photo"
                 onChange={(e) => fromPhoto(e.target.files?.[0])} />
        </label>
      </div>
      {scanning && <video ref={video} className="scan-video" muted playsInline aria-label="Camera preview" />}
      {error && <div className="alert alert-error small" role="alert">{error}</div>}

      {result && (
        <div className="card barcode-hit" data-testid="barcode-result">
          <div className="food-name">{result.name}</div>
          <div className="muted small">{result.brand} · barcode {result.barcode}</div>
          <div className="small">
            {result.serving_size ? (
              <>Per serving ({result.serving_label || "1 serving"}, {result.serving_size} {result.basis}):{" "}
                <strong>{Math.round(result.default_unit.nutrition.kcal)} kcal</strong>, P {result.default_unit.nutrition.protein_g} g,
                C {result.default_unit.nutrition.carb_g} g, F {result.default_unit.nutrition.fat_g} g</>
            ) : <>Per 100 {result.basis}: {result.per_100.kcal} kcal</>}
          </div>
          <div className="muted small">Source: {result.source_label} (FDC {result.source_ref}).</div>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => onFound(result)}>Log this product</button>
        </div>
      )}
      {notFound && (
        <div className="alert alert-info" role="status">
          <div>No product with barcode <strong>{notFound}</strong> is in Venn's offline sample.</div>
          <div className="btn-row">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onSearch}>Search foods</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onManual}>Enter manually</button>
          </div>
        </div>
      )}
      {samples.length > 0 && (
        <details className="samples">
          <summary className="small">Products in the offline barcode sample ({samples.length})</summary>
          <ul className="plain-list small">
            {samples.map((s) => (
              <li key={s.barcode}>
                <button type="button" className="link-btn" onClick={() => { setCode(s.barcode); lookup(s.barcode); }}>{s.barcode}</button>
                {" "}{s.brand}: {s.name.toLowerCase()}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ManualTab({ eatenAt, onSaved }: { eatenAt: string; onSaved: (e: FoodEntry) => void }) {
  const [f, setF] = useState({ description: "", kcal: "", protein_g: "", carb_g: "", fat_g: "", quantity: "1", eaten_at: eatenAt });
  const [errors, setErrors] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<ConfirmationNeeded | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => { setF((x) => ({ ...x, [k]: v })); setConfirm(null); };

  async function save(confirmed: boolean) {
    setBusy(true);
    setErrors([]);
    try {
      onSaved(await api.addManualEntry({
        description: f.description, kcal: Number(f.kcal), protein_g: Number(f.protein_g || 0),
        carb_g: Number(f.carb_g || 0), fat_g: Number(f.fat_g || 0), quantity: Number(f.quantity), eaten_at: f.eaten_at,
        confirm: confirmed,
      }));
    } catch (err) {
      const c = confirmationFrom(err);
      if (c) setConfirm(c);
      else setErrors(err instanceof ApiError ? err.details : ["Could not save."]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack" aria-label="Manual entry" onSubmit={(e) => { e.preventDefault(); save(false); }}>
      <p className="muted small">For foods not in the database. Enter the values for one serving from the label.</p>
      <label className="field"><span>Food description</span>
        <input id="m_description" value={f.description} onChange={(e) => set("description")(e.target.value)} maxLength={200} required />
      </label>
      <div className="row row-4">
        <label className="field"><span>Calories</span><input id="m_kcal" type="number" min="0" step="any" value={f.kcal} onChange={(e) => set("kcal")(e.target.value)} required /></label>
        <label className="field"><span>Protein g</span><input id="m_protein" type="number" min="0" step="any" value={f.protein_g} onChange={(e) => set("protein_g")(e.target.value)} /></label>
        <label className="field"><span>Carbs g</span><input id="m_carb" type="number" min="0" step="any" value={f.carb_g} onChange={(e) => set("carb_g")(e.target.value)} /></label>
        <label className="field"><span>Fat g</span><input id="m_fat" type="number" min="0" step="any" value={f.fat_g} onChange={(e) => set("fat_g")(e.target.value)} /></label>
      </div>
      <div className="row">
        <label className="field"><span>Servings</span><input id="m_qty" type="number" min="0" step="any" value={f.quantity} onChange={(e) => set("quantity")(e.target.value)} required /></label>
        <label className="field"><span>Date and time eaten</span><input id="m_time" type="datetime-local" value={f.eaten_at} onChange={(e) => set("eaten_at")(e.target.value)} required /></label>
      </div>
      {confirm && <ConfirmBox c={confirm} busy={busy} onSuggestion={() => undefined} onConfirm={() => save(true)} />}
      {errors.length > 0 && <div className="alert alert-error" role="alert">{errors.map((x) => <div key={x}>{x}</div>)}</div>}
      <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Add to log"}</button>
    </form>
  );
}
