// Display helpers for the Body page. Values are stored in kg / cm; these only format and convert.
import type { MeasurementEntry, MeasurementField, RecoveryState } from "../types";
import { CM_PER_INCH, KG_PER_LB } from "../units";

export type LengthUnit = "cm" | "in";

export const MEASUREMENT_LABELS: Record<MeasurementField, string> = {
  waist: "Waist", chest: "Chest", hips: "Hips", biceps: "Biceps", thigh: "Thigh",
};

export const STATE_COLORS: Record<RecoveryState, string> = {
  none: "#d4d4d8", low: "#fecaca", moderate: "#f87171", high: "#b91c1c",
};

export const STATE_SHORT: Record<RecoveryState, string> = {
  none: "Not assessed", low: "Low fatigue", moderate: "Moderate fatigue", high: "High fatigue",
};

export const round1 = (n: number) => Math.round(n * 10) / 10;

export function kgIn(kg: number, unit: "kg" | "lb"): number {
  return round1(unit === "lb" ? kg / KG_PER_LB : kg);
}

export function cmIn(cm: number, unit: LengthUnit): number {
  return round1(unit === "in" ? cm / CM_PER_INCH : cm);
}

/** "+0.4 kg", "-1.2 cm", "no change"; null when there is nothing to compare. */
export function signed(value: number | null, unit: string): string {
  if (value == null) return "-";
  const v = round1(value);
  if (v === 0) return "no change";
  return `${v > 0 ? "+" : "−"}${Math.abs(v)} ${unit}`;
}

/** Difference (in the display unit) between two entries for one field, or null if either is missing. */
export function fieldChange(latest: MeasurementEntry | undefined, base: MeasurementEntry | undefined, field: MeasurementField,
  unit: LengthUnit): number | null {
  const a = latest?.[`${field}_cm`];
  const b = base?.[`${field}_cm`];
  if (a == null || b == null) return null;
  return cmIn(a - b, unit);
}

export function shortDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function daysSinceText(days: number): string {
  if (days <= 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}
