import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NutrientBar from "../nutrition/NutrientBar";
import { rangeMessage } from "../nutrition/logic";
import {
  CUSTOM_DURATIONS, DURATION_CHOICES, durationLabel, GYM_LOCATIONS, proteinPerUnit, proteinReferenceKg,
} from "../profileModel";
import type { ProteinRange } from "../types";

const range = (eaten: number, state: ProteinRange["state"], to_low = 0, above_high = 0): ProteinRange =>
  ({ low: 171, high: 189, nominal: 180, eaten, state, to_low, above_high });

describe("protein range display", () => {
  it("explains below, within and above the range", () => {
    expect(rangeMessage(range(0, "below", 171))).toBe("Nothing logged yet; 171 g to reach your range.");
    expect(rangeMessage(range(150, "below", 21))).toBe("150 g eaten, 21 g to reach your range.");
    expect(rangeMessage(range(171, "within"))).toBe("171 g eaten, within your daily range.");
    expect(rangeMessage(range(200, "above", 0, 11))).toContain("11 g above your range. More protein isn't necessarily better.");
  });

  it("shows the range next to the protein bar", () => {
    render(<NutrientBar name="Protein" unit="g" tone="tone-protein" consumed={175.2} target={180} range={range(175, "within")} />);
    expect(screen.getByTestId("protein-range")).toHaveTextContent("Goal: 171–189 g · 175 g eaten, within your daily range.");
  });

  it("falls back to the plain bar when there is no target", () => {
    render(<NutrientBar name="Protein" unit="g" tone="tone-protein" consumed={40} target={null} range={null} />);
    expect(screen.queryByTestId("protein-range")).toBeNull();
    expect(screen.getByTestId("bar-protein")).toHaveTextContent("No target set");
  });
});

describe("protein reference weight and units", () => {
  it("uses the target weight only when losing scale weight with a lower target", () => {
    expect(proteinReferenceKg({ weight_kg: 110, target_weight_kg: 90, losing: true })).toBe(90);
    expect(proteinReferenceKg({ weight_kg: 110, target_weight_kg: 90, losing: false })).toBe(110);
    expect(proteinReferenceKg({ weight_kg: 80, target_weight_kg: null, losing: true })).toBe(80);
    expect(proteinReferenceKg({ weight_kg: null, target_weight_kg: 70, losing: true })).toBeNull();
  });

  it("shows the same multiplier per kg or per lb", () => {
    expect(proteinPerUnit(1.6, "kg")).toBe("1.6 g per kg");
    expect(proteinPerUnit(1.6, "lb")).toBe("0.73 g per lb");
    expect(proteinPerUnit(2.0, "lb")).toBe("0.91 g per lb");
    expect(proteinPerUnit(2.2, "lb")).toBe("1.00 g per lb");
  });
});

describe("durations and locations", () => {
  it("stores the top of each range and labels custom durations", () => {
    expect(DURATION_CHOICES.map((c) => c.id)).toEqual(["30", "45", "60", "75", "90", "105", "120", "custom"]);
    expect(durationLabel(45)).toBe("30–45 minutes");
    expect(durationLabel("150")).toBe("150 minutes (custom)");
    expect(durationLabel(50)).toBe("Up to 50 minutes");       // older custom values still display
    expect(CUSTOM_DURATIONS.every((d) => Number(d) > 120 && Number(d) % 15 === 0 && Number(d) <= 180)).toBe(true);
  });

  it("offers exactly six locations with sentence-case labels and preset equipment", () => {
    expect(GYM_LOCATIONS.map((g) => g.label)).toEqual([
      "Commercial gym", "Strength gym", "Local gym", "Home / garage gym", "Minimal equipment", "Bodyweight / outdoors"]);
    for (const g of GYM_LOCATIONS) expect(g.description).toMatch(/^[A-Z][^A-Z]*/);
    expect(GYM_LOCATIONS.find((g) => g.id === "bodyweight")!.equipment).toEqual([]);
    expect(GYM_LOCATIONS.find((g) => g.id === "commercial_gym")!.equipment).toEqual(expect.arrayContaining(["machine", "cable", "barbell"]));
  });
});
