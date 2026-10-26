// A tiny in-memory stand-in for the FastAPI backend, installed as global fetch.
import { vi } from "vitest";
import type { FoodDetail, FoodEntry, Macros, Profile, Target } from "../types";

export interface MockState {
  loggedIn: boolean;
  profile: Profile;
  target: Target | null;
  aiConfigured: boolean;
  requests: { method: string; path: string; body: unknown }[];
  manualError?: string[];
  entries: FoodEntry[];
}

export const COMPLETE_PROFILE: Profile = {
  sex: "male", birth_year: 1996, height_cm: 178, weight_kg: 82, activity_level: "moderate", goal: "lose",
  goal_rate_pct: 0.5, protein_level: "high", diet_style: "balanced", dietary_preferences: [],
  training_goal: "build_muscle", experience: "intermediate", days_per_week: 4, session_minutes: 75,
  equipment: ["barbell", "dumbbell"], preferred_split: "upper_lower", units: "metric", is_complete: true,
};

export const EMPTY_PROFILE: Profile = {
  sex: null, birth_year: null, height_cm: null, weight_kg: null, activity_level: null, goal: null,
  goal_rate_pct: 0, protein_level: "standard", diet_style: "balanced", dietary_preferences: [],
  training_goal: null, experience: null, days_per_week: null, session_minutes: null, equipment: [],
  preferred_split: "auto", units: "metric", is_complete: false,
};

export const TARGET: Target = {
  id: 1, method: "formula", kcal: 2390, protein_g: 164, carb_g: 255, fat_g: 80, created_at: "2026-10-25T00:00:00Z",
  breakdown: { bmr: 1773.5, activity_multiplier: 1.55, tdee: 2748.9, daily_energy_change: -451, minimum_kcal: 1773.5,
    minimum_applied: false, protein_capped: false, estimated_weekly_change_kg: -0.33, warnings: [] },
};

const macros = (kcal: number, protein_g: number, carb_g: number, fat_g: number): Macros => ({ kcal, protein_g, carb_g, fat_g });

export const CHICKEN: FoodDetail = {
  id: 11, name: "Chicken, broilers or fryers, breast, meat only, cooked, roasted", brand: "", category: "Poultry Products",
  source: "usda_sr_legacy", source_label: "USDA FoodData Central, SR Legacy", barcode: null, basis: "g",
  per_100: macros(165, 31.02, 0, 3.57), source_ref: "171477", published: "2019-04-01", serving_size: null, serving_label: "",
  default_unit: { unit: "portion:1", label: "1 cup, chopped or diced (140 g)", size: 140, nutrition: macros(231, 43.4, 0, 5) },
  units: [
    { unit: "portion:1", label: "1 cup, chopped or diced (140 g)", size: 140, kind: "count" },
    { unit: "g", label: "g", size: 1, kind: "mass" },
    { unit: "oz", label: "oz", size: 28.349523125, kind: "mass" },
  ],
};

export const QUEST: FoodDetail = {
  id: 22, name: "CHOCOLATE CHIP COOKIE DOUGH PROTEIN BARS", brand: "Quest", category: "Snack, Energy & Granola Bars",
  source: "usda_branded", source_label: "USDA FoodData Central, Branded Foods (manufacturer label)", barcode: "888849009305",
  basis: "g", per_100: macros(317, 35, 36.67, 15), source_ref: "2000001", published: "2024-01-01", serving_size: 60,
  serving_label: "1 bar", default_unit: { unit: "serving", label: "serving: 1 bar (60 g)", size: 60, nutrition: macros(190.2, 21, 22, 9) },
  units: [{ unit: "serving", label: "serving: 1 bar (60 g)", size: 60, kind: "count" }, { unit: "g", label: "g", size: 1, kind: "mass" }],
};

const FOODS: Record<number, FoodDetail> = { [CHICKEN.id]: CHICKEN, [QUEST.id]: QUEST };
const NUTRIENTS = ["kcal", "protein_g", "carb_g", "fat_g"] as const;

const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function progress(consumed: number, target: number | null) {
  if (target == null) return { consumed, target: null, remaining: null, over: null, percent: null, state: "no_target" };
  const state = Math.round(consumed) === Math.round(target) ? "met" : consumed === 0 ? "empty" : consumed < target ? "partial" : "over";
  return { consumed, target, remaining: Math.max(target - consumed, 0), over: Math.max(consumed - target, 0), percent: (consumed / target) * 100, state };
}

function makeEntry(id: number, food: FoodDetail, quantity: number, unit: string, eatenAt: string): FoodEntry {
  const u = food.units.find((x) => x.unit === unit)!;
  const amount = quantity * u.size;
  const r = (per100: number) => Math.round((per100 * amount) / 10) / 10;
  return {
    id, food_id: food.id, kind: "catalog", description: food.name, brand: food.brand, quantity, unit, unit_label: u.label,
    amount, basis: food.basis, kcal: r(food.per_100.kcal), protein_g: r(food.per_100.protein_g), carb_g: r(food.per_100.carb_g),
    fat_g: r(food.per_100.fat_g), eaten_at: eatenAt, local_date: eatenAt.slice(0, 10), units: food.units, source_label: food.source_label,
  };
}

export function seedEntry(state: MockState, food: FoodDetail, quantity: number, unit: string, eatenAt: string) {
  state.entries.push(makeEntry(state.entries.length + 100, food, quantity, unit, eatenAt));
}

function nutritionRoute(state: MockState, method: string, path: string, body: Record<string, unknown> | undefined): Response | null {
  const url = new URL(path, "http://test");
  const p = url.pathname;
  if (method === "GET" && p === "/api/nutrition/day") {
    const date = url.searchParams.get("date")!;
    const entries = state.entries.filter((e) => e.local_date === date).sort((a, b) => a.eaten_at.localeCompare(b.eaten_at));
    const totals = macros(0, 0, 0, 0);
    for (const e of entries) for (const k of NUTRIENTS) totals[k] += e[k];
    const t = state.target;
    return json(200, {
      date, entries, totals,
      target: t ? { id: t.id, method: t.method, kcal: t.kcal, protein_g: t.protein_g, carb_g: t.carb_g, fat_g: t.fat_g } : null,
      progress: Object.fromEntries(NUTRIENTS.map((k) => [k, progress(totals[k], t ? t[k] : null)])),
    });
  }
  if (method === "GET" && p === "/api/nutrition/week") {
    const end = url.searchParams.get("end")!;
    const days = new Set(state.entries.map((e) => e.local_date));
    return json(200, { start: end, end, days: [{ date: end, entries: state.entries.length, kcal: 0 }], days_logged: days.size });
  }
  if (method === "GET" && p === "/api/foods/search") {
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    return json(200, { query: q, results: Object.values(FOODS).filter((f) => f.name.toLowerCase().includes(q) || f.brand.toLowerCase().includes(q)) });
  }
  if (method === "GET" && p === "/api/foods/recent") {
    const seen = new Map<number, FoodEntry>();
    for (const e of [...state.entries].reverse()) if (e.food_id && !seen.has(e.food_id)) seen.set(e.food_id, e);
    return json(200, {
      results: [...seen.values()].map((e) => ({
        ...FOODS[e.food_id!], times_logged: 1,
        last: { quantity: e.quantity, unit: e.unit, unit_label: e.unit_label, kcal: e.kcal, eaten_at: e.eaten_at },
      })),
    });
  }
  if (method === "GET" && p === "/api/foods/barcodes") {
    return json(200, { products: [{ barcode: QUEST.barcode, name: QUEST.name, brand: "Quest" }] });
  }
  const bc = p.match(/^\/api\/foods\/barcode\/(.+)$/);
  if (method === "GET" && bc) {
    const code = decodeURIComponent(bc[1]);
    if (!/^\d+$/.test(code)) return json(422, { detail: ["A barcode contains digits only."] });
    if (code === QUEST.barcode) return json(200, QUEST);
    return json(404, { detail: { code: "barcode_not_found", message: "This barcode isn't in Venn's offline product sample.", barcode: code } });
  }
  const fm = p.match(/^\/api\/foods\/(\d+)$/);
  if (method === "GET" && fm) return FOODS[Number(fm[1])] ? json(200, FOODS[Number(fm[1])]) : json(404, { detail: "Food not found." });
  if (method === "POST" && p === "/api/nutrition/entries") {
    const b = body as unknown as { food_id: number; quantity: number; unit: string; eaten_at: string; confirm?: boolean };
    const food = FOODS[b.food_id];
    const unit = food.units.find((u) => u.unit === b.unit)!;
    if (unit.kind === "count" && b.quantity >= 20 && !b.confirm) {
      return json(409, {
        detail: {
          code: "confirmation_required", warnings: [`${b.quantity} servings is unusual. Did you mean ${b.quantity} g?`],
          suggestions: [{ quantity: b.quantity, unit: "g", label: `Use ${b.quantity} g instead` }],
          preview: macros((food.per_100.kcal * b.quantity * unit.size) / 100, 0, 0, 0),
        },
      });
    }
    const e = makeEntry(state.entries.length + 100, food, b.quantity, b.unit, b.eaten_at);
    state.entries.push(e);
    return json(201, e);
  }
  const em = p.match(/^\/api\/nutrition\/entries\/(\d+)$/);
  if (em && method === "DELETE") {
    state.entries = state.entries.filter((e) => e.id !== Number(em[1]));
    return json(204, null);
  }
  return null;
}

export function installMockBackend(initial: Partial<MockState> = {}): MockState {
  const state: MockState = {
    loggedIn: false, profile: COMPLETE_PROFILE, target: TARGET, aiConfigured: false, requests: [], entries: [], ...initial,
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    state.requests.push({ method, path, body });
    const key = `${method} ${path}`;

    if (key === "GET /api/health") {
      return json(200, { status: "ok", app: "Venn", version: "0.2.0", database: "ok",
        ai: { configured: state.aiConfigured, model: "gpt-6-luna", provider: "portkey",
          message: state.aiConfigured ? null : "AI features are disabled: PORTKEY_API_KEY is not set." } });
    }
    if (key === "POST /api/auth/login") {
      if (body.password !== "right-password") return json(401, { detail: "Incorrect username or password." });
      state.loggedIn = true;
      return json(200, { id: 1, username: body.username, display_name: "Demo Athlete" });
    }
    if (key === "GET /api/options") {
      return json(200, { equipment: ["body only", "dumbbell", "barbell", "kettlebells", "bands"], dietary_preferences: ["vegetarian", "dairy_free"],
        disclaimer: "These targets are estimates ... not medical advice." });
    }
    if (!state.loggedIn) return json(401, { detail: "Please log in." });
    const nutritionResponse = nutritionRoute(state, method, path, body);
    if (nutritionResponse) return nutritionResponse;

    switch (key) {
      case "GET /api/auth/me": return json(200, { id: 1, username: "demo", display_name: "Demo Athlete" });
      case "POST /api/auth/logout": state.loggedIn = false; return json(204, null);
      case "GET /api/profile": return json(200, state.profile);
      case "PUT /api/profile":
        if (body.weight_kg > 300) return json(422, { detail: [{ loc: ["body", "weight_kg"], msg: "Input should be less than or equal to 300" }] });
        state.profile = { ...body, is_complete: true };
        return json(200, { profile: state.profile, target_updated: true, target: state.target });
      case "GET /api/targets/current": return json(200, { target: state.target, disclaimer: "not medical advice" });
      case "POST /api/targets/manual":
        if (state.manualError) return json(422, { detail: state.manualError });
        state.target = { ...TARGET, ...body, id: 2, method: "manual", breakdown: {} };
        return json(201, state.target);
      case "GET /api/limitations": return json(200, []);
      default: return json(404, { detail: `No mock for ${key}` });
    }
  });
  vi.stubGlobal("fetch", fetchMock);
  return state;
}
