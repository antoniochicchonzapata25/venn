// Pure helpers for the training UI (tested in src/test/trainingLogic.test.ts).
import type { WorkoutExercise } from "../types";

export const KG_PER_LB = 0.45359237;

export function fromKg(kg: number | null, unit: "kg" | "lb"): number | null {
  if (kg == null) return null;
  return unit === "lb" ? Math.round((kg / KG_PER_LB) * 10) / 10 : Math.round(kg * 10) / 10;
}

export function targetText(e: Pick<WorkoutExercise, "target_sets" | "rep_low" | "rep_high" | "target_seconds" | "measure">): string {
  if (e.measure === "time") return `${e.target_sets} × ${e.target_seconds} s`;
  const reps = e.rep_low === e.rep_high ? `${e.rep_high}` : `${e.rep_low}–${e.rep_high}`;
  return `${e.target_sets} × ${reps} reps`;
}

export function restText(seconds: number): string {
  return seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} min rest` : seconds >= 60
    ? `${Math.floor(seconds / 60)} min ${seconds % 60} s rest` : `${seconds} s rest`;
}

/** "14 min over plan", "3 min under plan" or "On plan". */
export function differenceText(diff: number | null): string {
  if (diff == null) return "Not finished";
  if (diff === 0) return "On plan";
  return `${Math.abs(diff)} min ${diff > 0 ? "over" : "under"} plan`;
}

export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  return `${h ? `${h}:` : ""}${mm}:${String(sec).padStart(2, "0")}`;
}

/** Prefill for the next set: the last logged set, else the suggestion from history. */
export function nextSetDefaults(e: WorkoutExercise, unit: "kg" | "lb"): { weight: string; reps: string; seconds: string } {
  const last = e.sets[e.sets.length - 1];
  const weightKg = last?.weight_kg ?? e.suggested_weight_kg;
  const w = fromKg(weightKg, unit);
  return {
    weight: w == null ? "" : String(w),
    reps: String(last?.reps ?? e.rep_high ?? ""),
    seconds: String(last?.duration_seconds ?? e.target_seconds ?? ""),
  };
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const EQUIPMENT_ICON: Record<string, string> = { "body only": "body weight" };
