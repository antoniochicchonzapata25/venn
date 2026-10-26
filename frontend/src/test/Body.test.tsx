import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { fieldChange, signed } from "../body/logic";
import type { MeasurementEntry, Recovery, RecoveryGroup, WeightHistory } from "../types";
import { COMPLETE_PROFILE, installMockBackend } from "./mockBackend";

afterEach(() => vi.unstubAllGlobals());

const GROUPS: [RecoveryGroup["id"], string][] = [["back", "Back"], ["biceps", "Biceps"], ["chest", "Chest"], ["shoulders", "Shoulders"],
  ["triceps", "Triceps"], ["lower_back", "Lower back"], ["abs", "Abs"], ["glutes", "Glutes"], ["hamstrings", "Hamstrings"], ["quadriceps", "Quadriceps"]];

const MODEL: Recovery["model"] = {
  window_days: 7, decay_hours: 72, moderate_at: 2, high_at: 5, explanation: "Each logged set counts 1.0 for a primary group.",
  disclaimer: "An estimate from your logged workouts, not a medically validated recovery rule.",
  states: { none: "Not assessed", low: "Low", moderate: "Moderate", high: "High" },
};

function recovery(withHistory: boolean): Recovery {
  const groups = GROUPS.map(([id, label]): RecoveryGroup => ({
    id, label, state: "none", state_label: "", residual: 0, weighted_sets_7d: 0, last_workout: null, exercises: [] }));
  if (!withHistory) return { has_history: false, last_workout: null, counts: { low: 0, moderate: 0, high: 0, none: 10 }, groups, model: MODEL, soreness: {} };
  const lw = { id: 9, name: "Upper Body", finished_at: "2026-10-25T18:00:00Z", hours_ago: 20, is_demo: false, local_date: "2026-10-25" };
  const chest = groups.find((g) => g.id === "chest")!;
  Object.assign(chest, { state: "high", residual: 5.2, weighted_sets_7d: 6, last_workout: lw,
    exercises: [{ name: "Barbell Bench Press", sets: 4, role: "primary", weighted_sets: 4 }, { name: "Push-Ups", sets: 2, role: "primary", weighted_sets: 2 }] });
  Object.assign(groups.find((g) => g.id === "triceps")!, { state: "moderate", residual: 2.6, weighted_sets_7d: 3, last_workout: lw,
    exercises: [{ name: "Barbell Bench Press", sets: 4, role: "secondary", weighted_sets: 2 }] });
  Object.assign(groups.find((g) => g.id === "abs")!, { state: "low", residual: 0, weighted_sets_7d: 3, last_workout: { ...lw, id: 4, name: "Full Body" } });
  return { has_history: true, counts: { low: 1, moderate: 1, high: 1, none: 7 }, groups, model: MODEL, soreness: {},
    last_workout: { id: 9, name: "Upper Body", finished_at: lw.finished_at, is_demo: false, local_date: "2026-10-25", days_since: 1, groups_trained: 3 } };
}

function installBody(opts: { units?: "kg" | "lb"; history?: boolean } = {}) {
  installMockBackend({ loggedIn: true, profile: { ...COMPLETE_PROFILE, weight_unit: opts.units ?? "kg", height_unit: opts.units === "lb" ? "ft_in" : "cm" } });
  const base = globalThis.fetch;
  const weights: WeightHistory = { entries: [], latest: null, previous: null, change_kg: null, days_between: null, note: "Recorded values only." };
  let nextId = 1;
  const rec = recovery(opts.history ?? true);
  const calls: { method: string; path: string; body: unknown }[] = [];
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (!path.startsWith("/api/body")) return base(input, init);
    calls.push({ method, path, body });
    if (path === "/api/body/weights" && method === "GET") return json(200, weights);
    if (path === "/api/body/weights" && method === "POST") {
      const kg = body.unit === "lb" ? body.weight * 0.45359237 : body.weight;
      if (kg < 25) return json(422, { detail: [`${body.weight} ${body.unit} looks implausible. Enter a body weight between 25-350 kg.`] });
      weights.entries = [{ id: nextId++, entry_date: body.entry_date, weight_kg: kg }, ...weights.entries]
        .sort((a, b) => b.entry_date.localeCompare(a.entry_date));
      weights.latest = weights.entries[0];
      weights.previous = weights.entries[1] ?? null;
      weights.change_kg = weights.previous ? weights.latest.weight_kg - weights.previous.weight_kg : null;
      weights.days_between = weights.previous ? 7 : null;
      return json(201, weights);
    }
    if (path === "/api/body/measurements") {
      return json(200, { entries: [], fields: ["waist", "chest", "hips", "biceps", "thigh"], note: "",
        comparison: Object.fromEntries(["waist", "chest", "hips", "biceps", "thigh"].map((f) => [f,
          { latest_cm: null, latest_date: null, previous_cm: null, previous_date: null, change_cm: null }])) });
    }
    if (path.startsWith("/api/body/recovery")) return json(200, rec);
    if (path === "/api/body/soreness/chest" && method === "PUT") {
      return json(200, { muscle_group: "chest", rating: body.rating, recorded_at: "2026-10-26T15:00:00Z" });
    }
    return json(404, { detail: `No body mock for ${method} ${path}` });
  }));
  return { calls, weights };
}

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("body: progress", () => {
  it("shows empty states, rejects implausible weights, then compares latest and previous", async () => {
    const { calls } = installBody();
    renderAt("/body");
    const user = userEvent.setup();
    const card = await screen.findByRole("region", { name: "Body weight" });
    expect(await within(card).findByText("No entries yet")).toBeInTheDocument();
    expect(screen.getByText(/No measurements yet/)).toBeInTheDocument();

    await user.type(within(card).getByLabelText("Weight (kg)"), "12");
    await user.click(within(card).getByRole("button", { name: "Save weight" }));
    expect(await within(card).findByRole("alert")).toHaveTextContent("looks implausible");

    const date = within(card).getByLabelText("Date");
    await user.clear(date);
    await user.type(date, "2026-10-19");
    const weight = within(card).getByLabelText("Weight (kg)");
    await user.clear(weight);
    await user.type(weight, "82.4");
    await user.click(within(card).getByRole("button", { name: "Save weight" }));
    await user.clear(date);
    await user.type(date, "2026-10-26");
    await user.type(weight, "81.9");
    await user.click(within(card).getByRole("button", { name: "Save weight" }));
    await waitFor(() => expect(within(card).getByTestId("weight-change")).toHaveTextContent("−0.5 kg"));
    expect(within(card).getByRole("img", { name: /Weight chart: 2 entries/ })).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").at(-1)?.body).toEqual({ entry_date: "2026-10-26", weight: 81.9, unit: "kg" });
  });

  it("sends and shows weights in lb for imperial users", async () => {
    const { calls } = installBody({ units: "lb" });
    renderAt("/body");
    const user = userEvent.setup();
    const card = await screen.findByRole("region", { name: "Body weight" });
    await user.type(within(card).getByLabelText("Weight (lb)"), "180");
    await user.click(within(card).getByRole("button", { name: "Save weight" }));
    expect((await within(card).findAllByText("180 lb")).length).toBeGreaterThan(0);
    expect(calls.at(-1)?.body).toMatchObject({ weight: 180, unit: "lb" });
    expect(screen.getByLabelText("Waist (in)")).toBeInTheDocument();
  });
});

describe("body: recovery", () => {
  it("switches views with the segmented toggle and shows indicators from the data", async () => {
    installBody();
    renderAt("/body");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Recovery" }));
    expect(screen.getByRole("tab", { name: "Recovery" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByTestId("days-since")).toHaveTextContent("1 day");
    expect(screen.getByText("3 of 10")).toBeInTheDocument();
    expect(screen.getByTestId("count-low")).toHaveTextContent("1");
    expect(screen.getByTestId("count-moderate")).toHaveTextContent("1");
    expect(screen.getByTestId("count-high")).toHaveTextContent("1");
    expect(screen.getByTestId("count-none")).toHaveTextContent("7");
    // every one of the ten groups is a separate, labelled, clickable region (shoulders appear front and back)
    for (const [, label] of GROUPS) expect(screen.getAllByRole("button", { name: new RegExp(`^${label}:`) }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Chest: High fatigue" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Lower back: Not assessed" })).toHaveLength(1);
    expect(screen.getByText(/not a medically validated/)).toBeInTheDocument();
  });

  it("opens a detail panel with logged exercises and keeps soreness separate", async () => {
    const { calls } = installBody();
    renderAt("/body?view=recovery");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Chest: High fatigue" }));
    const panel = screen.getByRole("region", { name: "Chest details" });
    expect(within(panel).getByText("High fatigue")).toBeInTheDocument();
    expect(within(panel).getByText(/Barbell Bench Press: 4 logged sets \(primary muscle/)).toBeInTheDocument();
    expect(within(panel).getByText(/Estimated remaining load:/)).toHaveTextContent("5.2");
    await user.type(within(panel).getByLabelText("Rating (0–10)"), "6");
    await user.click(within(panel).getByRole("button", { name: "Save rating" }));
    expect(await within(panel).findByText("6/10")).toBeInTheDocument();
    expect(within(panel).getByText("High fatigue")).toBeInTheDocument();  // estimate unchanged by the rating
    expect(calls.at(-1)).toMatchObject({ method: "PUT", path: "/api/body/soreness/chest", body: { rating: 6 } });
    // keyboard access: a region can be selected with Enter
    screen.getAllByRole("button", { name: "Triceps: Moderate fatigue" })[0].focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("region", { name: "Triceps details" })).toHaveTextContent("secondary muscle, counted as 2 weighted sets");
  });

  it("shows an explicit no-data state instead of inventing recovery values", async () => {
    installBody({ history: false });
    renderAt("/body?view=recovery");
    expect(await screen.findByText(/No completed workouts yet/)).toBeInTheDocument();
    expect(screen.getByText("No completed workout recorded.")).toBeInTheDocument();
    expect(screen.getByTestId("count-none")).toHaveTextContent("10");
    expect(screen.queryByRole("button", { name: /High fatigue|Moderate fatigue|Low fatigue/ })).toBeNull();
  });
});

describe("body: logic", () => {
  it("formats signed differences and compares only recorded fields", () => {
    expect(signed(-0.04, "kg")).toBe("no change");
    expect(signed(1.26, "cm")).toBe("+1.3 cm");
    expect(signed(null, "cm")).toBe("-");
    const a = { id: 1, entry_date: "2026-10-26", waist_cm: 86.5, chest_cm: null, hips_cm: 99, biceps_cm: null, thigh_cm: null } as MeasurementEntry;
    const b = { id: 2, entry_date: "2026-10-12", waist_cm: 88, chest_cm: 104, hips_cm: null, biceps_cm: null, thigh_cm: null } as MeasurementEntry;
    expect(fieldChange(a, b, "waist", "cm")).toBe(-1.5);
    expect(fieldChange(a, b, "waist", "in")).toBe(-0.6);
    expect(fieldChange(a, b, "chest", "cm")).toBeNull();
    expect(fieldChange(a, b, "hips", "cm")).toBeNull();
  });
});
