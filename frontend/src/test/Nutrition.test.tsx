import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { localDate } from "../nutrition/logic";
import { CHICKEN, QUEST, installMockBackend, seedEntry } from "./mockBackend";

afterEach(() => vi.unstubAllGlobals());

const today = localDate();
const renderNutrition = () => render(<MemoryRouter initialEntries={["/nutrition"]}><App /></MemoryRouter>);

describe("nutrition dashboard", () => {
  it("shows the empty state with targets and nothing logged", async () => {
    installMockBackend({ loggedIn: true });
    renderNutrition();
    expect(await screen.findByText(/Nothing logged for today yet/)).toBeInTheDocument();
    expect(screen.getByTestId("bar-calories")).toHaveTextContent("Nothing logged yet · 2,390 kcal left");
  });

  it("lists entries chronologically with totals and remaining amounts", async () => {
    const state = installMockBackend({ loggedIn: true });
    seedEntry(state, CHICKEN, 200, "g", `${today}T19:30`);
    seedEntry(state, QUEST, 1, "serving", `${today}T08:15`);
    renderNutrition();
    const log = await screen.findByRole("region", { name: "Food log" });
    const times = within(log).getAllByRole("listitem").map((li) => li.querySelector("time")!.textContent);
    expect(times).toEqual(["08:15", "19:30"]);
    // 200 g chicken = 330 kcal; 1 Quest bar (60 g) = 190.2 kcal; total 520.2 -> 520; 2,390 - 520.2 = 1,869.8 -> 1,870
    expect(screen.getByTestId("bar-calories")).toHaveTextContent("520 kcal");
    expect(screen.getByTestId("bar-calories")).toHaveTextContent("1,870 kcal left");
  });

  it("shows over-target amounts", async () => {
    const state = installMockBackend({ loggedIn: true });
    seedEntry(state, CHICKEN, 1000, "g", `${today}T12:00`); // 310.2 g protein vs 164 g target
    renderNutrition();
    expect(await screen.findByTestId("bar-protein")).toHaveTextContent("146.2 g over");
  });

  it("explains a missing target instead of inventing one", async () => {
    const state = installMockBackend({ loggedIn: true, target: null });
    seedEntry(state, CHICKEN, 100, "g", `${today}T12:00`);
    renderNutrition();
    expect(await screen.findByText(/No nutrition target is set for this date/)).toBeInTheDocument();
    expect(screen.getByTestId("bar-calories")).toHaveTextContent("165 kcal");
    expect(screen.queryAllByRole("progressbar")).toHaveLength(0);
  });
});

describe("add food flow", () => {
  it("searches, picks a food, adjusts the quantity and saves it with a timestamp", async () => {
    const state = installMockBackend({ loggedIn: true });
    const { container } = renderNutrition();
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: /add food/i }))[0]);
    const dialog = await screen.findByRole("dialog", { name: "Add food" });
    await user.click(within(dialog).getByRole("tab", { name: "Search" }));
    await user.type(within(dialog).getByRole("searchbox", { name: "Search foods" }), "chicken");
    await user.click(await within(dialog).findByRole("button", { name: /Chicken, broilers/ }));

    const qty = container.querySelector("#qty") as HTMLInputElement;
    await user.selectOptions(container.querySelector("#unit") as HTMLSelectElement, "g");
    await user.clear(qty);
    await user.type(qty, "150");
    expect(screen.getByTestId("preview")).toHaveTextContent("248 kcal"); // 247.5 rounds to 248 on screen
    const time = container.querySelector("#eaten_at") as HTMLInputElement;
    await user.clear(time);
    await user.type(time, `${today}T07:30`);
    await user.click(screen.getByRole("button", { name: "Add to log" }));

    await waitFor(() => expect(state.entries).toHaveLength(1));
    const sent = state.requests.find((r) => r.method === "POST")!.body as Record<string, unknown>;
    expect(sent).toMatchObject({ food_id: CHICKEN.id, quantity: 150, unit: "g", eaten_at: `${today}T07:30` });
    expect(await screen.findByRole("status")).toHaveTextContent("Added Chicken · 248 kcal");
  });

  it("re-uses a recent food with its last quantity", async () => {
    const state = installMockBackend({ loggedIn: true });
    seedEntry(state, QUEST, 2, "serving", "2026-10-20T10:00");
    const { container } = renderNutrition();
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: /add food/i }))[0]);
    const recent = await screen.findByRole("list", { name: "Recently used foods" });
    await user.click(within(recent).getByRole("button", { name: /PROTEIN BARS/ }));
    expect((container.querySelector("#qty") as HTMLInputElement).value).toBe("2");
    expect((container.querySelector("#unit") as HTMLSelectElement).value).toBe("serving");
  });

  it("flags an implausible quantity and applies the suggested correction", async () => {
    const state = installMockBackend({ loggedIn: true });
    const { container } = renderNutrition();
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: /add food/i }))[0]);
    const dialog = await screen.findByRole("dialog", { name: "Add food" });
    await user.click(within(dialog).getByRole("tab", { name: "Barcode" }));
    await user.type(container.querySelector("#barcode") as HTMLInputElement, QUEST.barcode!);
    await user.click(within(dialog).getByRole("button", { name: "Look up" }));
    expect(await screen.findByTestId("barcode-result")).toHaveTextContent("Quest");
    await user.click(screen.getByRole("button", { name: "Log this product" }));
    const qty = container.querySelector("#qty") as HTMLInputElement;
    await user.clear(qty);
    await user.type(qty, "150");
    await user.click(screen.getByRole("button", { name: "Add to log" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Did you mean 150 g?");
    expect(state.entries).toHaveLength(0); // nothing saved yet
    await user.click(screen.getByRole("button", { name: "Use 150 g instead" }));
    await waitFor(() => expect(state.entries).toHaveLength(1));
    expect(state.entries[0]).toMatchObject({ quantity: 150, unit: "g", kcal: 475.5 });
  });

  it("offers search or manual entry for an unknown barcode", async () => {
    installMockBackend({ loggedIn: true });
    const { container } = renderNutrition();
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: /add food/i }))[0]);
    const dialog = await screen.findByRole("dialog", { name: "Add food" });
    await user.click(within(dialog).getByRole("tab", { name: "Barcode" }));
    await user.type(container.querySelector("#barcode") as HTMLInputElement, "036000291452");
    await user.click(within(dialog).getByRole("button", { name: "Look up" }));
    const msg = await within(dialog).findByText(/is in Venn's offline sample/);
    expect(msg).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Enter manually" }));
    expect(within(dialog).getByRole("form", { name: "Manual entry" })).toBeInTheDocument();
  });
});
