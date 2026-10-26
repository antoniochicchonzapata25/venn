import { describe, expect, it } from "vitest";
import { clock, differenceText, fromKg, nextSetDefaults, restText, targetText } from "../training/logic";
import type { WorkoutExercise } from "../types";

const exercise = (over: Partial<WorkoutExercise> = {}): WorkoutExercise => ({
  id: 1, position: 0, exercise_id: "Barbell_Bench_Press_-_Medium_Grip", name: "Bench", pattern: "push_h", role: "main",
  measure: "reps", target_sets: 3, rep_low: 6, rep_high: 10, target_seconds: null, rest_seconds: 120, est_minutes: 6.3,
  instructions: [], notes: [], suggested_weight_kg: null, suggested_weight_lb: null, last_summary: null,
  replaced_exercise_id: null, completed: false, equipment: ["barbell", "bench"], sets: [], ...over,
});

describe("training display logic", () => {
  it("formats targets for reps and timed exercises", () => {
    expect(targetText(exercise())).toBe("3 × 6–10 reps");
    expect(targetText(exercise({ measure: "time", target_seconds: 40, rep_low: null, rep_high: null }))).toBe("3 × 40 s");
  });
  it("formats rest", () => {
    expect(restText(120)).toBe("2 min rest");
    expect(restText(75)).toBe("1 min 15 s rest");
    expect(restText(45)).toBe("45 s rest");
  });
  it("describes planned vs actual difference", () => {
    expect(differenceText(14)).toBe("14 min over plan");
    expect(differenceText(-3)).toBe("3 min under plan");
    expect(differenceText(0)).toBe("On plan");
    expect(differenceText(null)).toBe("Not finished");
  });
  it("converts kg to lb for display", () => {
    expect(fromKg(60, "lb")).toBe(132.3);
    expect(fromKg(61.23, "kg")).toBe(61.2);
    expect(fromKg(null, "lb")).toBeNull();
  });
  it("formats elapsed time", () => {
    expect(clock(65)).toBe("1:05");
    expect(clock(3725)).toBe("1:02:05");
  });
  it("prefills the next set from the last set, else the suggestion", () => {
    expect(nextSetDefaults(exercise({ suggested_weight_kg: 60 }), "kg")).toEqual({ weight: "60", reps: "10", seconds: "" });
    const logged = exercise({ sets: [{ id: 9, set_index: 1, reps: 8, weight_kg: 62.5, weight_lb: 137.8, duration_seconds: null, logged_at: "" }] });
    expect(nextSetDefaults(logged, "lb").weight).toBe("137.8");
    expect(nextSetDefaults(logged, "kg").reps).toBe("8");
  });
});
