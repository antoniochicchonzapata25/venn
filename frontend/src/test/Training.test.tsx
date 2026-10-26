import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { Workout, WorkoutExercise } from "../types";
import { installMockBackend } from "./mockBackend";

afterEach(() => vi.unstubAllGlobals());

const ex = (id: number, name: string, over: Partial<WorkoutExercise> = {}): WorkoutExercise => ({
  id, position: id, exercise_id: name.replace(/ /g, "_"), name, pattern: "pull_h", role: "main", measure: "reps",
  target_sets: 3, rep_low: 6, rep_high: 10, target_seconds: null, rest_seconds: 120, est_minutes: 6,
  instructions: ["Sit tall."], notes: [], suggested_weight_kg: null, suggested_weight_lb: null, last_summary: null,
  replaced_exercise_id: null, completed: false, equipment: ["cable"], sets: [], ...over,
});

function makeWorkout(): Workout {
  return {
    id: 7, status: "planned", name: "Upper Body", split: "upper_lower", day_type: "upper", goal: "build_muscle",
    objective: "Build muscle.", generator: "deterministic-v1", budget_minutes: 75, planned_minutes: 64, is_demo: false,
    created_at: "2026-10-25T17:00:00Z", started_at: null, finished_at: null, summary: null,
    explanation: ["Estimated 64 min of your 75-minute budget.", "This is general fitness guidance, not medical advice."],
    exercises: [ex(1, "Seated Cable Rows", { notes: ["Loads the lower back moderately."] }), ex(2, "Side Lateral Raise", { role: "accessory", equipment: ["dumbbell"] })],
    exercise_source: "free-exercise-db",
  };
}

/** Adds /api/training/* routes on top of the shared mock backend. */
function installTraining(opts: { units?: "kg" | "lb"; generateError?: boolean } = {}) {
  const state = installMockBackend({ loggedIn: true });
  const base = globalThis.fetch;
  let w = makeWorkout();
  const calls: { method: string; path: string; body: unknown }[] = [];
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (!path.startsWith("/api/training")) return base(input, init);
    calls.push({ method, path, body });
    if (path === "/api/training/options") {
      return json(200, { split: "upper_lower", split_reason: "an upper/lower split", day_types: [], next_day_type: "upper",
        all_day_types: [{ id: "upper", name: "Upper Body" }, { id: "lower", name: "Lower Body" }], session_minutes: 75, units: opts.units ?? "kg",
        preferred_split: "upper_lower", splits: [{ id: "auto", name: "Automatic" }, { id: "upper_lower", name: "Upper / lower" }] });
    }
    if (path === "/api/training/summary") {
      return json(200, { planned: null, in_progress: null, completed_last_7_days: 1, days_per_week: 4, sessions_compared: 1,
        average_difference_minutes: 17, history: [{ ...makeWorkout(), id: 3, status: "completed", is_demo: true, name: "Lower Body",
          finished_at: "2026-10-23T18:41:00Z", planned_minutes: 58, summary: { actual_minutes: 71, planned_minutes: 58, difference_minutes: 13 } }] });
    }
    if (path === "/api/training/generate") {
      if (opts.generateError) return json(422, { detail: { code: "cannot_generate", message: "Venn couldn't build a useful Push workout.", alternatives: ["Add equipment in Settings."] } });
      return json(201, w);
    }
    if (path === "/api/training/workouts/7" && method === "GET") return json(200, w);
    if (path === "/api/training/workouts/7/exercises/1/alternatives") {
      return json(200, { exercise: "Seated Cable Rows", message: null, alternatives: [
        { id: "Leverage_Iso_Row", name: "Leverage Iso Row", pattern: "pull_h", pattern_label: "row", equipment: ["machine"], level: "beginner",
          primary_muscles: ["lats"], reason: "Same movement pattern: row; trains lats.", notes: [] }] });
    }
    if (path === "/api/training/workouts/7/exercises/1/replace") {
      w = { ...w, exercises: [ex(1, "Leverage Iso Row", { exercise_id: "Leverage_Iso_Row", replaced_exercise_id: "Seated_Cable_Rows", equipment: ["machine"] }), w.exercises[1]] };
      return json(200, w);
    }
    if (path === "/api/training/workouts/7/start") {
      w = { ...w, status: "in_progress", started_at: new Date().toISOString() };
      return json(200, w);
    }
    if (path === "/api/training/workouts/7/sets") {
      const b = body as { workout_exercise_id: number; reps: number; weight: number; unit: string };
      const kg = b.unit === "lb" ? Math.round(b.weight * 0.45359237 * 100) / 100 : b.weight;
      w = { ...w, exercises: w.exercises.map((e) => e.id !== b.workout_exercise_id ? e : { ...e,
        sets: [...e.sets, { id: 50 + e.sets.length, set_index: e.sets.length + 1, reps: b.reps, weight_kg: kg, weight_lb: null, duration_seconds: null, logged_at: "" }] }) };
      return json(201, w);
    }
    if (path === "/api/training/workouts/7/finish") {
      w = { ...w, status: "completed", finished_at: new Date().toISOString(),
        summary: { planned_minutes: 64, actual_minutes: 78, difference_minutes: 14, sets_logged: 1, sets_planned: 6,
          exercises_completed: 0, exercises_planned: 2, volume_kg: 600, records: [] } };
      return json(200, w);
    }
    return json(404, { detail: `No training mock for ${method} ${path}` });
  }));
  return { state, calls };
}

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("training", () => {
  it("shows history with planned vs actual and marks demo data", async () => {
    installTraining();
    renderAt("/training");
    const history = await screen.findByRole("region", { name: "Workout history" });
    expect(await within(history).findByText("Lower Body")).toBeInTheDocument();
    expect(within(history).getByText("Demo data")).toBeInTheDocument();
    expect(within(history).getByText("13 min over plan")).toBeInTheDocument();
  });

  it("runs the whole lifecycle: generate, review, replace, start, log in lb, finish", async () => {
    const { calls } = installTraining({ units: "lb" });
    renderAt("/training");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Generate workout" }));
    expect(await screen.findByRole("region", { name: "Why this workout" })).toHaveTextContent("not medical advice");
    expect(screen.getByText(/Loads the lower back moderately/)).toBeInTheDocument();

    // replace: choose from the server's compatible list
    const rows = screen.getByRole("listitem", { name: "Seated Cable Rows" });
    await user.click(within(rows).getByRole("button", { name: "Replace" }));
    const sheet = await screen.findByRole("dialog", { name: "Replace exercise" });
    await user.click(within(sheet).getByRole("button", { name: /Leverage Iso Row/ }));
    expect(await screen.findByRole("listitem", { name: "Leverage Iso Row" })).toHaveTextContent("You swapped this in for Seated Cable Rows");

    // start and log a set in pounds
    await user.click(screen.getByRole("button", { name: "Start workout" }));
    const form = await screen.findByRole("form", { name: "Log set for Leverage Iso Row" });
    await user.type(within(form).getByLabelText("Weight in lb"), "135");
    await user.clear(within(form).getByLabelText("Reps"));
    await user.type(within(form).getByLabelText("Reps"), "10");
    await user.click(within(form).getByRole("button", { name: "✓ Log set" }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/sets"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/sets"))!.body).toMatchObject({ workout_exercise_id: 1, reps: 10, weight: 135, unit: "lb" });
    expect(await screen.findByText(/10 reps × 135 lb/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Rest");

    await user.click(screen.getByRole("button", { name: "Finish workout" }));
    const summary = await screen.findByRole("region", { name: "Workout summary" });
    expect(summary).toHaveTextContent("78 min");
    expect(summary).toHaveTextContent("64 min");
    expect(summary).toHaveTextContent("14 min over plan");
  });

  it("explains when a workout cannot be generated", async () => {
    installTraining({ generateError: true });
    renderAt("/training");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Generate workout" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("couldn't build a useful Push workout");
    expect(alert).toHaveTextContent("Add equipment in Settings.");
  });
});
