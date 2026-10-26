import type {
  AiCheck, Alternative, CoachMetrics, CoachRun, CoachStatus, ConfirmationNeeded, DaySummary, FoodDetail, FoodEntry, FoodSummary, Health, Limitation, Options,
  Profile, ProfileInput, RecentFood, Target, TrainingOptions, TrainingSummary, User, WeekSummary, Workout, WorkoutBrief,
} from "./types";

export class ApiError extends Error {
  status: number;
  details: string[];
  body: unknown;

  constructor(status: number, details: string[], body?: unknown) {
    super(details.join(" "));
    this.status = status;
    this.details = details;
    this.body = body;
  }
}

/** Turn FastAPI error bodies (string, list of strings, pydantic errors, or a {message|warnings} object) into lines. */
function readDetail(body: unknown): string[] {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return [detail];
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      if (typeof d === "string") return d;
      const item = d as { msg?: string; loc?: (string | number)[] };
      const field = item.loc?.filter((p) => p !== "body").join(" ");
      const msg = (item.msg ?? "Invalid value").replace(/^Value error, /, "");
      return field ? `${field.replace(/_/g, " ")}: ${msg}` : msg;
    });
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; warnings?: string[] };
    if (d.message) return [d.message];
    if (d.warnings) return d.warnings;
  }
  return ["Something went wrong. Please try again."];
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, readDetail(data), data);
  return data as T;
}

export interface NewEntry {
  food_id: number;
  quantity: number;
  unit: string;
  eaten_at: string;
  confirm?: boolean;
}

export interface NewManualEntry {
  description: string;
  kcal: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
  quantity: number;
  eaten_at: string;
  confirm?: boolean;
}

export const api = {
  health: () => request<Health>("GET", "/api/health"),
  checkAi: () => request<AiCheck>("POST", "/api/health/ai"),

  me: () => request<User>("GET", "/api/auth/me"),
  login: (username: string, password: string) => request<User>("POST", "/api/auth/login", { username, password }),
  register: (username: string, password: string, display_name: string) =>
    request<User>("POST", "/api/auth/register", { username, password, display_name }),
  logout: () => request<void>("POST", "/api/auth/logout"),

  options: () => request<Options>("GET", "/api/options"),
  profile: () => request<Profile>("GET", "/api/profile"),
  saveProfile: (p: ProfileInput) =>
    request<{ profile: Profile; target_updated: boolean; target: Target | null }>("PUT", "/api/profile", p),

  currentTarget: () => request<{ target: Target | null; disclaimer: string }>("GET", "/api/targets/current"),
  recalculate: () => request<Target>("POST", "/api/targets/recalculate"),
  setManualTarget: (t: { kcal: number; protein_g: number; carb_g: number; fat_g: number }) =>
    request<Target>("POST", "/api/targets/manual", t),

  limitations: () => request<Limitation[]>("GET", "/api/limitations"),
  addLimitation: (l: Omit<Limitation, "id" | "created_at" | "updated_at">) =>
    request<Limitation>("POST", "/api/limitations", l),
  updateLimitation: (id: number, l: Omit<Limitation, "id" | "created_at" | "updated_at">) =>
    request<Limitation>("PUT", `/api/limitations/${id}`, l),
  deleteLimitation: (id: number) => request<void>("DELETE", `/api/limitations/${id}`),

  searchFoods: (q: string) =>
    request<{ results: FoodSummary[] }>("GET", `/api/foods/search?q=${encodeURIComponent(q)}&limit=20`),
  recentFoods: () => request<{ results: RecentFood[] }>("GET", "/api/foods/recent"),
  food: (id: number) => request<FoodDetail>("GET", `/api/foods/${id}`),
  barcode: (code: string) => request<FoodDetail>("GET", `/api/foods/barcode/${encodeURIComponent(code)}`),
  sampleBarcodes: () =>
    request<{ products: { barcode: string; name: string; brand: string }[] }>("GET", "/api/foods/barcodes"),

  day: (date: string) =>
    request<DaySummary>("GET", `/api/nutrition/day?date=${date}&tz_offset=${new Date().getTimezoneOffset()}`),
  week: (end: string) => request<WeekSummary>("GET", `/api/nutrition/week?end=${end}`),
  addEntry: (e: NewEntry) => request<FoodEntry>("POST", "/api/nutrition/entries", e),
  addManualEntry: (e: NewManualEntry) => request<FoodEntry>("POST", "/api/nutrition/entries/manual", e),
  editEntry: (id: number, e: { quantity?: number; unit?: string; eaten_at?: string; confirm?: boolean }) =>
    request<FoodEntry>("PATCH", `/api/nutrition/entries/${id}`, e),
  deleteEntry: (id: number) => request<void>("DELETE", `/api/nutrition/entries/${id}`),

  trainingOptions: () => request<TrainingOptions>("GET", "/api/training/options"),
  trainingSummary: () => request<TrainingSummary>("GET", "/api/training/summary"),
  generateWorkout: (b: { day_type?: string | null; minutes?: number; variant?: number; split?: string }) =>
    request<Workout>("POST", "/api/training/generate", b),
  workout: (id: number) => request<Workout>("GET", `/api/training/workouts/${id}`),
  discardWorkout: (id: number) => request<void>("DELETE", `/api/training/workouts/${id}`),
  alternatives: (id: number, weId: number) =>
    request<{ exercise: string; alternatives: Alternative[]; message: string | null }>(
      "GET", `/api/training/workouts/${id}/exercises/${weId}/alternatives`),
  replaceExercise: (id: number, weId: number, exercise_id: string) =>
    request<Workout>("POST", `/api/training/workouts/${id}/exercises/${weId}/replace`, { exercise_id }),
  startWorkout: (id: number) => request<Workout>("POST", `/api/training/workouts/${id}/start`),
  logSet: (id: number, b: { workout_exercise_id: number; reps?: number | null; weight?: number | null; unit: string;
    duration_seconds?: number | null }) => request<Workout>("POST", `/api/training/workouts/${id}/sets`, b),
  deleteSet: (id: number, setId: number) => request<Workout>("DELETE", `/api/training/workouts/${id}/sets/${setId}`),
  markExercise: (id: number, weId: number, completed: boolean) =>
    request<Workout>("PATCH", `/api/training/workouts/${id}/exercises/${weId}`, { completed }),
  finishWorkout: (id: number) => request<Workout>("POST", `/api/training/workouts/${id}/finish`),

  coachStatus: () => request<CoachStatus>("GET", "/api/coach/status"),
  coachAsk: (question: string, workflow: string, localDate: string) =>
    request<CoachRun | { status: "disabled" | "error"; message: string }>("POST", "/api/coach/ask",
      { question, workflow, local_date: localDate, tz_offset: new Date().getTimezoneOffset() }),
  coachRuns: () => request<{ runs: CoachRun[] }>("GET", "/api/coach/runs"),
  coachRun: (id: number) => request<CoachRun>("GET", `/api/coach/runs/${id}`),
  coachMetrics: (day: string) =>
    request<CoachMetrics>("GET", `/api/coach/metrics?day=${day}&tz_offset=${new Date().getTimezoneOffset()}`),
};

export type { WorkoutBrief };

/** If the server asked for confirmation (HTTP 409), return its warnings and suggested fixes. */
export function confirmationFrom(err: unknown): ConfirmationNeeded | null {
  if (err instanceof ApiError && err.status === 409) {
    const detail = (err.body as { detail?: ConfirmationNeeded } | null)?.detail;
    if (detail?.code === "confirmation_required") return detail;
  }
  return null;
}
