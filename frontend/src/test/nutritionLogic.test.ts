import { describe, expect, it } from "vitest";
import {
  barSegments, defaultEatenAt, friendlyDate, localDate, localDateTime, previewNutrition, quantityText, shiftDate,
} from "../nutrition/logic";

describe("barSegments (progress bar visual states)", () => {
  it("shows an all-remaining bar when nothing is eaten", () => {
    expect(barSegments(0, 2000)).toEqual({ filled: 0, remaining: 100, over: 0, state: "empty" });
  });
  it("splits filled and remaining when partially complete", () => {
    expect(barSegments(500, 2000)).toEqual({ filled: 25, remaining: 75, over: 0, state: "partial" });
  });
  it("treats an exact (rounded) match as met", () => {
    expect(barSegments(2000.4, 2000)).toEqual({ filled: 100, remaining: 0, over: 0, state: "met" });
    expect(barSegments(164, 164).state).toBe("met");
  });
  it("rescales the bar when over target: target part filled, excess marked over", () => {
    // 2,500 eaten vs 2,000 target: bar = 2,500, target = 80%, over = 20%
    expect(barSegments(2500, 2000)).toEqual({ filled: 80, remaining: 0, over: 20, state: "over" });
    const big = barSegments(6000, 2000);
    expect(big.filled + big.over).toBeCloseTo(100, 5);
  });
  it("reports missing targets instead of inventing one", () => {
    expect(barSegments(800, null).state).toBe("no_target");
    expect(barSegments(800, 0).state).toBe("no_target");
  });
});

describe("previewNutrition", () => {
  it("matches the backend formula", () => {
    const per100 = { kcal: 165, protein_g: 31.02, carb_g: 0, fat_g: 3.57 };
    expect(previewNutrition(per100, 150, { unit: "g", label: "g", size: 1, kind: "mass" }))
      .toEqual({ kcal: 247.5, protein_g: 46.5, carb_g: 0, fat_g: 5.4 });
    expect(previewNutrition(per100, 1, { unit: "portion:1", label: "1 cup", size: 140, kind: "count" })?.kcal).toBe(231);
  });
  it("returns null for invalid quantities", () => {
    const per100 = { kcal: 100, protein_g: 1, carb_g: 1, fat_g: 1 };
    const g = { unit: "g", label: "g", size: 1, kind: "mass" } as const;
    expect(previewNutrition(per100, 0, g)).toBeNull();
    expect(previewNutrition(per100, -2, g)).toBeNull();
    expect(previewNutrition(per100, Number.NaN, g)).toBeNull();
  });
});

describe("local dates and times", () => {
  it("uses the local calendar, not UTC", () => {
    const lateEvening = new Date(2026, 9, 25, 23, 45); // 25 Oct 23:45 local time
    expect(localDate(lateEvening)).toBe("2026-10-25");
    expect(localDateTime(lateEvening)).toBe("2026-10-25T23:45");
  });
  it("shifts days across month boundaries", () => {
    expect(shiftDate("2026-10-31", 1)).toBe("2026-11-01");
    expect(shiftDate("2026-03-01", -1)).toBe("2026-02-28");
  });
  it("defaults a past day's entry to that day at the current clock time", () => {
    expect(defaultEatenAt("2026-10-20", new Date(2026, 9, 25, 8, 5))).toBe("2026-10-20T08:05");
  });
  it("labels today and yesterday", () => {
    expect(friendlyDate("2026-10-25", "2026-10-25")).toBe("Today");
    expect(friendlyDate("2026-10-24", "2026-10-25")).toBe("Yesterday");
  });
  it("formats quantities for the log", () => {
    expect(quantityText(150, "g", "g")).toBe("150 g");
    expect(quantityText(1, "serving: 1 bar (60 g)", "serving")).toBe("1 × 1 bar (60 g)");
    expect(quantityText(1, "serving: 125 g (125 g)", "serving")).toBe("1 × 125 g");
  });
});
