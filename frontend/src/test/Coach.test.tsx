import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import type { CoachRun } from "../types";
import { installMockBackend } from "./mockBackend";

afterEach(() => vi.unstubAllGlobals());

const RUN: CoachRun = {
  id: 5, question: "How am I doing against my protein goal?", workflow: "nutrition", routed_by: "keywords", status: "ok",
  answer: "Your protein range is 156-172 g. Today you have logged 82.2 g.", error: null, model: "gpt-6-luna",
  model_calls: 2, tool_calls: 2, latency_ms: 2400, tools_used: ["get_nutrition_targets", "get_daily_nutrition"],
  usage: { input_tokens: 2100, cached_input_tokens: 0, output_tokens: 180, reasoning_tokens: 60, complete: true },
  estimated_cost_usd: 0.0003, created_at: "2026-10-26T15:00:00Z", price_source: "MGT 409 class slide",
  checks: { grounded: true, numbers_checked: 3, numbers_verified: 3, unverified_numbers: [], untrusted_text_flags: [],
            exercises_mentioned: [], exercise_conflicts: [] },
  trace: [{ step: "router", method: "keywords", workflow: "nutrition" }, { step: "tool_call", tool: "get_nutrition_targets", ok: true }],
};

function installCoach(opts: { enabled: boolean; run?: CoachRun }) {
  installMockBackend({ loggedIn: true });
  const base = globalThis.fetch;
  const calls: { path: string; body: unknown }[] = [];
  const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (!path.startsWith("/api/coach")) return base(input, init);
    calls.push({ path, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (path === "/api/coach/status") {
      return json({ enabled: opts.enabled, model: "gpt-6-luna", runs_today: 0, daily_limit: 40,
        message: opts.enabled ? null : "The AI Coach is unavailable because no API key is configured. Nutrition, training and your numbers below still work." });
    }
    if (path === "/api/coach/runs") return json({ runs: [] });
    if (path.startsWith("/api/coach/metrics")) {
      return json({ window_days: 7, nutrition: { days_logged: 4, average_protein_g_on_logged_days: 120.5, days_within_protein_range: 1, days_below_protein_range: 3 },
        training: { completed_workouts: 2, of_which_demo_data: 2, average_minutes_over_plan: 18.5 }, body_measurements: "not tracked in Venn yet" });
    }
    if (path === "/api/coach/ask") return json(opts.run ?? RUN);
    return new Response("{}", { status: 404 });
  }));
  return calls;
}

const renderCoach = () => render(<MemoryRouter initialEntries={["/coach"]}><App /></MemoryRouter>);

describe("AI Coach page", () => {
  it("asks a question and shows a grounded answer with tools, tokens, cost and trace", async () => {
    const calls = installCoach({ enabled: true });
    renderCoach();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "How am I doing against my protein goal?" }));
    await user.click(screen.getByRole("button", { name: "Ask" }));
    const card = await screen.findByRole("region", { name: "Coach answer" });
    expect(within(card).getByTestId("coach-answer")).toHaveTextContent("156-172 g");
    expect(card).toHaveTextContent("Nutrition Agent");
    expect(card).toHaveTextContent("✓ 3 numbers match your records");
    expect(card).toHaveTextContent("get_nutrition_targets, get_daily_nutrition");
    expect(card).toHaveTextContent("2,100 input (0 cached) + 180 output tokens");
    expect(card).toHaveTextContent("Run trace #5");
    expect(calls.find((c) => c.path === "/api/coach/ask")!.body).toMatchObject({ question: "How am I doing against my protein goal?", workflow: "auto" });
  });

  it("shows grounding and safety warnings instead of hiding them", async () => {
    installCoach({ enabled: true, run: { ...RUN, checks: { grounded: false, numbers_checked: 1, numbers_verified: 0, unverified_numbers: [999],
      untrusted_text_flags: ["instruction-like text in user data was neutralised"], exercises_mentioned: ["Barbell Squat"],
      exercise_conflicts: [{ exercise: "Barbell Squat", reasons: ["loads the lower back heavily"] }] } } });
    renderCoach();
    const user = userEvent.setup();
    await screen.findByText(/gpt-6-luna · 0\/40 today/);   // wait until the coach is enabled
    await user.type(screen.getByLabelText("Your question"), "Alternatives to squats?");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    const checks = await screen.findByRole("group", { name: "Checks" });
    expect(checks).toHaveTextContent("Not found in your records: 999");
    expect(checks).toHaveTextContent("Barbell Squat conflicts with your profile");
    expect(checks).toHaveTextContent("neutralised");
  });

  it("shows a clear unavailable state without an API key, and still shows calculated numbers", async () => {
    installCoach({ enabled: false });
    renderCoach();
    expect(await screen.findByText(/AI Coach is unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    const numbers = await screen.findByRole("region", { name: "Your numbers" });
    expect(numbers).toHaveTextContent("Calculated by Venn from your records, not by AI");
    expect(await within(numbers).findByText("120.5 g")).toBeInTheDocument();
    expect(screen.queryByTestId("coach-answer")).toBeNull();
  });
});
