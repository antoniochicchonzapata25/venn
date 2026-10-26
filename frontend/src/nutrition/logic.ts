// Pure helpers for the nutrition UI (tested in src/test/nutritionLogic.test.ts).
import type { Macros, UnitOption } from "../types";

const pad = (n: number) => String(n).padStart(2, "0");

/** Local calendar date as YYYY-MM-DD (never UTC, so late-evening entries stay on the right day). */
export function localDate(d: Date = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Local wall-clock time as YYYY-MM-DDTHH:MM, the format the API stores. */
export function localDateTime(d: Date = new Date()): string {
  return `${localDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Default time for a new entry on `day`: the current clock time on that day. */
export function defaultEatenAt(day: string, now: Date = new Date()): string {
  return `${day}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

export function shiftDate(day: string, days: number): string {
  const [y, m, d] = day.split("-").map(Number);
  return localDate(new Date(y, m - 1, d + days));
}

export function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Same formula as the backend: value per 100 x quantity x unit size / 100 (display preview only). */
export function previewNutrition(per100: Macros, quantity: number, unit: UnitOption | undefined): Macros | null {
  if (!unit || !Number.isFinite(quantity) || quantity <= 0) return null;
  const amount = quantity * unit.size;
  return {
    kcal: round1((per100.kcal * amount) / 100),
    protein_g: round1((per100.protein_g * amount) / 100),
    carb_g: round1((per100.carb_g * amount) / 100),
    fat_g: round1((per100.fat_g * amount) / 100),
  };
}

export interface BarSegments {
  filled: number; // % of bar width shown as consumed (up to the target)
  remaining: number; // % lightly shaded: still available
  over: number; // % marked as above the target
  state: "no_target" | "empty" | "partial" | "met" | "over";
}

/**
 * Horizontal bar layout. Under target, the bar represents the target: consumed is filled and the
 * rest is shaded. Over target, the bar represents what was eaten: the target part is filled and the
 * excess is marked as over. "met" matches the backend: equal when rounded to whole units.
 */
export function barSegments(consumed: number, target: number | null): BarSegments {
  if (target == null || target <= 0) return { filled: 0, remaining: 0, over: 0, state: "no_target" };
  const c = Math.max(0, consumed);
  if (Math.round(c) === Math.round(target)) return { filled: 100, remaining: 0, over: 0, state: "met" };
  if (c === 0) return { filled: 0, remaining: 100, over: 0, state: "empty" };
  if (c < target) {
    const filled = round1((c / target) * 100);
    return { filled, remaining: round1(100 - filled), over: 0, state: "partial" };
  }
  const filled = round1((target / c) * 100);
  return { filled, remaining: 0, over: round1(100 - filled), state: "over" };
}

export function fmt(n: number, unit: "kcal" | "g"): string {
  const v = unit === "kcal" ? Math.round(n) : round1(n);
  return `${v.toLocaleString()} ${unit}`;
}

export function formatTime(eatenAt: string): string {
  return eatenAt.slice(11, 16);
}

export function friendlyDate(day: string, today: string = localDate()): string {
  if (day === today) return "Today";
  if (day === shiftDate(today, -1)) return "Yesterday";
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

/** Short quantity text for a log row, e.g. "150 g" or "1 × 1 cup (158 g)". */
export function quantityText(quantity: number, unitLabel: string, unit: string): string {
  const q = Number.isInteger(quantity) ? String(quantity) : String(round1(quantity));
  // "serving: 125 g (125 g)" -> "125 g": drop the size in brackets when it repeats the label
  const label = unitLabel.replace(/^serving: /, "").replace(/^(.+) \(\1\)$/, "$1");
  if (unit.startsWith("portion:") || unit === "serving") return `${q} × ${label}`;
  return `${q} ${unitLabel}`;
}

/** Text for the protein range (computed by the backend from the unrounded target). */
export function rangeMessage(r: { eaten: number; low: number; high: number; state: string; to_low: number; above_high: number }): string {
  if (r.state === "within") return `${r.eaten} g eaten, within your daily range.`;
  if (r.state === "below") return r.eaten === 0 ? `Nothing logged yet; ${r.to_low} g to reach your range.` : `${r.eaten} g eaten, ${r.to_low} g to reach your range.`;
  return `${r.eaten} g eaten, ${r.above_high} g above your range. More protein isn't necessarily better.`;
}
