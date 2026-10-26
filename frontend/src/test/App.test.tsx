import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { EMPTY_PROFILE, installMockBackend } from "./mockBackend";

function renderAt(path = "/") {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

afterEach(() => vi.unstubAllGlobals());

describe("authentication", () => {
  it("shows the Venn sign-in page when logged out, with the demo hint", async () => {
    installMockBackend();
    renderAt();
    expect(await screen.findByRole("heading", { name: "Venn" })).toBeInTheDocument();
    expect(screen.getByText(/venn-demo-2026/)).toBeInTheDocument();
  });

  it("shows the server's error on a wrong password, then logs in", async () => {
    installMockBackend();
    const { container } = renderAt();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Username"), "demo");
    await user.type(container.querySelector('input[type="password"]')!, "wrong-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password.");

    const pwd = container.querySelector('input[type="password"]') as HTMLInputElement;
    await user.clear(pwd);
    await user.type(pwd, "right-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("heading", { name: "Hi, Demo Athlete" })).toBeInTheDocument();
  });
});

describe("dashboard", () => {
  it("shows targets and clearly marks AI as disabled without a key", async () => {
    installMockBackend({ loggedIn: true, aiConfigured: false });
    renderAt();
    expect(await screen.findByText("2,390")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Protein: 0 g of 164 g" })).toBeInTheDocument();
    expect(screen.getByTestId("ai-badge")).toHaveTextContent("Disabled");
    expect(screen.getByText(/AI features are disabled/)).toBeInTheDocument();
  });

  it("sends a new user to the setup questionnaire, which they can skip", async () => {
    installMockBackend({ loggedIn: true, profile: EMPTY_PROFILE, target: null });
    renderAt();
    expect(await screen.findByRole("heading", { name: "What's your main goal right now?" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Setup progress" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("link", { name: "Skip for now" }));
    expect(await screen.findByRole("link", { name: "Complete your profile" })).toHaveAttribute("href", "/welcome");
    expect(screen.getByText(/No nutrition target is set for this date/)).toBeInTheDocument();
  });

  it("shows every module in the navigation", async () => {
    installMockBackend({ loggedIn: true });
    renderAt();
    const nav = await screen.findByRole("navigation", { name: "Main" });
    for (const name of ["Home", "Nutrition", "Training", "Body", "Coach", "Settings"]) {
      expect(nav).toHaveTextContent(name);
    }
  });
});

describe("settings", () => {
  it("switches units beside each field and saves metric values", async () => {
    const state = installMockBackend({ loggedIn: true, profile: EMPTY_PROFILE, target: null });
    const { container } = renderAt("/settings");
    const user = userEvent.setup();
    await screen.findByRole("form", { name: "Profile" });
    const sel = (id: string) => container.querySelector(`#${id}`) as HTMLSelectElement;
    const inp = (id: string) => container.querySelector(`#${id}`) as HTMLInputElement;
    const unitButton = (field: string, unit: string) =>
      within(screen.getByRole("group", { name: `${field} unit` })).getByRole("button", { name: unit });

    await user.selectOptions(sel("sex"), "female");
    await user.type(inp("birth_year"), "1990");
    await user.click(unitButton("Height", "ft/in"));
    await user.type(inp("height_ft"), "5");
    await user.type(inp("height_in"), "5");          // 5 ft 5 in = 165.1 cm
    await user.click(unitButton("Weight", "lb"));
    await user.type(inp("weight"), "150");           // 150 lb = 68.04 kg
    // switching back and forth only changes the display, never the stored value
    for (let n = 0; n < 5; n++) {
      await user.click(unitButton("Weight", "kg"));
      expect(inp("weight").value).toBe("68");
      await user.click(unitButton("Weight", "lb"));
      expect(inp("weight").value).toBe("150");
    }
    await user.click(unitButton("Height", "cm"));
    expect(inp("height").value).toBe("165.1");
    await user.selectOptions(sel("activity_level"), "light");
    await user.selectOptions(sel("goal"), "maintain");
    await user.selectOptions(sel("training_goal"), "general_fitness");
    await user.selectOptions(sel("experience"), "beginner");
    await user.selectOptions(sel("days_per_week"), "3");
    await user.selectOptions(sel("session_minutes"), "45");
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(state.requests.some((r) => r.method === "PUT")).toBe(true));
    const sent = state.requests.find((r) => r.method === "PUT")!.body as Record<string, number | string | null>;
    expect(sent.session_minutes).toBe(45);
    expect(sent.height_cm).toBeCloseTo(165.1, 2);
    expect(sent.weight_kg).toBeCloseTo(68.039, 3);
    expect(sent.weight_unit).toBe("lb");
    expect(sent.height_unit).toBe("cm");
    expect(sent.goal).toBe("maintain");
    expect(sent.goal_rate_pct).toBe(0);
    expect(sent.target_weight_kg).toBeNull();          // no forced target weight
    expect(await screen.findByRole("status")).toHaveTextContent("calculated targets were updated");
  });

  it("maps clear goal choices onto the calculator and shows protein in grams", async () => {
    const state = installMockBackend({ loggedIn: true });
    const { container } = renderAt("/settings");
    const user = userEvent.setup();
    await screen.findByRole("form", { name: "Profile" });
    await user.selectOptions(container.querySelector("#goal") as HTMLSelectElement, "lose_fat");
    await user.selectOptions(container.querySelector("#pace") as HTMLSelectElement, "gradual");
    await user.selectOptions(container.querySelector("#protein_level") as HTMLSelectElement, "very_high");
    expect(screen.getByText(/180 g of protein a day/)).toBeInTheDocument();   // 82 kg x 2.2
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    await waitFor(() => expect(state.requests.some((r) => r.method === "PUT")).toBe(true));
    const sent = state.requests.find((r) => r.method === "PUT")!.body as Record<string, unknown>;
    expect(sent).toMatchObject({ goal: "lose", goal_rate_pct: 0.25, goal_focus: "fat_loss", protein_level: "very_high" });
  });

  it("shows server validation errors for profile fields", async () => {
    installMockBackend({ loggedIn: true });
    const { container } = renderAt("/settings");
    const user = userEvent.setup();
    await screen.findByRole("form", { name: "Profile" });
    const weight = container.querySelector("#weight") as HTMLInputElement;
    await user.clear(weight);
    await user.type(weight, "500");
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("weight kg: Input should be less than or equal to 300");
  });

  it("rejects manual targets below the safety minimum with the server's reason", async () => {
    installMockBackend({ loggedIn: true, manualError: ["calories must be at least 1500 kcal (Venn's safety minimum)"] });
    const { container } = renderAt("/settings");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Set my own targets" }));
    const kcal = container.querySelector("#manual_kcal") as HTMLInputElement;
    await user.clear(kcal);
    await user.type(kcal, "1000");
    await user.click(screen.getByRole("button", { name: "Save my targets" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 1500 kcal");
    expect(screen.getByTestId("target-kcal")).toHaveTextContent("2,390");
  });
});
