import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { goalFields, PACE_RATES, proteinGrams, emptyModel } from "../profileModel";
import { cmToFtIn, formatHeight, ftInToCm, kgToLb, lbToKg, parseWeight, weightText } from "../units";
import { EMPTY_PROFILE, installMockBackend } from "./mockBackend";

afterEach(() => vi.unstubAllGlobals());

describe("unit conversions", () => {
  it("converts height both ways", () => {
    expect(ftInToCm(5, 10)).toBeCloseTo(177.8, 6);
    expect(cmToFtIn(177.8)).toEqual({ ft: 5, inches: 10 });
    expect(cmToFtIn(182.88)).toEqual({ ft: 6, inches: 0 });  // 72 in exactly
    expect(cmToFtIn(182.7)).toEqual({ ft: 5, inches: 11.9 }); // 71.93 in
    expect(cmToFtIn(182.85)).toEqual({ ft: 6, inches: 0 });   // 71.99 in rounds to 6 ft 0, never "5 ft 12 in"
    expect(formatHeight(165.1, "ft_in")).toBe("5 ft 5 in");
  });

  it("converts weight without drifting when switching repeatedly", () => {
    expect(lbToKg(150)).toBeCloseTo(68.0389, 4);
    expect(kgToLb(100)).toBeCloseTo(220.462, 3);
    let kg = parseWeight("150", "lb")!;
    for (let i = 0; i < 100; i++) {
      // display in kg, then in lb, from the same stored value
      expect(weightText(kg, "kg")).toBe("68");
      expect(weightText(kg, "lb")).toBe("150");
      kg = parseWeight(weightText(kg, "lb"), "lb")!;   // even re-parsing the display keeps it stable
    }
    expect(parseWeight("", "kg")).toBeNull();
    expect(parseWeight("abc", "kg")).toBeNull();
  });
});

describe("goal and protein mapping", () => {
  it("maps user-facing goals onto the existing calculator", () => {
    const m = { ...emptyModel(), pace: "moderate" as const };
    expect(goalFields({ ...m, goalChoice: "lose_fat", changeScale: true })).toEqual({ goal: "lose", goal_rate_pct: 0.5, goal_focus: "fat_loss" });
    expect(goalFields({ ...m, goalChoice: "lose_fat", changeScale: false })).toEqual({ goal: "maintain", goal_rate_pct: 0, goal_focus: "recomp" });
    expect(goalFields({ ...m, goalChoice: "gain_muscle", changeScale: true })).toEqual({ goal: "gain", goal_rate_pct: 0.25, goal_focus: "muscle_gain" });
    expect(goalFields({ ...m, goalChoice: "maintain", changeScale: true }).goal).toBe("maintain");
    // every pace stays inside the backend safety limits (1.0% lose, 0.5% gain per week)
    expect(Math.max(...Object.values(PACE_RATES.lose))).toBeLessThanOrEqual(1.0);
    expect(Math.max(...Object.values(PACE_RATES.gain))).toBeLessThanOrEqual(0.5);
  });

  it("shows protein as grams per day", () => {
    expect(proteinGrams(70, "standard")).toBe(112);   // 70 x 1.6
    expect(proteinGrams(70, "very_high")).toBe(154);  // 70 x 2.2
    expect(proteinGrams(null, "high")).toBeNull();
  });
});

describe("onboarding questionnaire", () => {
  it("asks one question per screen and saves the answers to the profile", async () => {
    const state = installMockBackend({ loggedIn: true, profile: EMPTY_PROFILE, target: null });
    const { container } = render(<MemoryRouter initialEntries={["/welcome"]}><App /></MemoryRouter>);
    const user = userEvent.setup();
    const pick = async (group: string, option: RegExp) =>
      user.click(within(await screen.findByRole("radiogroup", { name: group })).getByRole("radio", { name: option }));
    const next = () => user.click(screen.getByRole("button", { name: "Continue" }));

    await pick("Goal", /Lose body fat/); await next();
    await pick("Scale weight", /No, keep my weight/); await next();      // recomposition: no pace step
    await pick("Sex", /^Female/);
    await user.type(container.querySelector("#ob_birth") as HTMLInputElement, "1992"); await next();
    await user.type(container.querySelector("#ob_height") as HTMLInputElement, "168");
    await user.click(within(screen.getByRole("group", { name: "Weight unit" })).getByRole("button", { name: "lb" }));
    await user.type(container.querySelector("#ob_weight") as HTMLInputElement, "140"); await next();
    await pick("Daily activity", /Lightly active/); await next();
    await pick("Training goal", /Build muscle/); await next();
    await pick("Experience", /Beginner/); await next();
    await pick("Strength days", /^3 days/); await next();
    await pick("Duration", /30–45 minutes/); await next();
    await pick("Workout location", /Minimal equipment/);
    // the preset pre-selects equipment, which stays editable
    expect(screen.getByRole("checkbox", { name: "dumbbell" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "bands" })).toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "bands" }));
    await user.click(screen.getByRole("checkbox", { name: "kettlebells" })); await next();
    await pick("Cardio schedule", /On separate days/); await next();
    await pick("Cardio days", /^4 days/); await next();
    await pick("Cardio duration", /^30 minutes/); await next();
    await user.selectOptions(container.querySelector("#ob_ability_pushups") as HTMLSelectElement, "5_9");
    await user.selectOptions(container.querySelector("#ob_ability_pullups") as HTMLSelectElement, "none"); await next();
    await pick("Protein", /Balanced/);
    expect(screen.getByRole("radio", { name: /Balanced/ })).toHaveTextContent("0.91 g per lb, about 127 g a day");  // 63.5 kg x 2.0
    await next();
    await pick("Eating pattern", /^Other/);
    expect(screen.getByRole("button", { name: "Finish" })).toBeDisabled();   // "Other" needs details
    await user.type(container.querySelector("#ob_pattern_other") as HTMLInputElement, "Low-FODMAP");
    expect(screen.getByRole("button", { name: "Back" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Finish" }));

    await waitFor(() => expect(state.requests.some((r) => r.method === "PUT")).toBe(true));
    const sent = state.requests.find((r) => r.method === "PUT")!.body as Record<string, unknown>;
    expect(sent).toMatchObject({
      goal: "maintain", goal_focus: "recomp", sex: "female", birth_year: 1992, height_cm: 168, weight_unit: "lb",
      activity_level: "light", training_goal: "build_muscle", experience: "beginner", days_per_week: 3, session_minutes: 45,
      gym_location: "minimal", cardio_schedule: "separate_days", cardio_sessions_per_week: 4, cardio_minutes: 30,
      cardio_in_plan: false, exercise_ability: { pushups: "5_9", pullups: "none" }, protein_level: "high",
      eating_pattern: "other", eating_pattern_other: "Low-FODMAP", target_weight_kg: null,
    });
    expect([...(sent.equipment as string[])].sort()).toEqual(["dumbbell", "kettlebells"]);
    expect(sent.weight_kg as number).toBeCloseTo(63.503, 3);
  });
});
