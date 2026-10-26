// Shared profile model for Settings and onboarding: questions, answer options, and API mapping.
import type { Profile, ProfileInput } from "./types";
import type { HeightUnit, WeightUnit } from "./units";

export interface Choice { id: string; label: string; description?: string }

/** Primary body-composition goal shown to the user; mapped onto the calculator's goal + pace. */
export type GoalChoice = "lose_fat" | "maintain" | "gain_muscle";
export type Pace = "gradual" | "moderate" | "faster";

// % of body weight per week. Must match backend/app/services/goal_projection.py PACE_RATES.
export const PACE_RATES: Record<"lose" | "gain", Record<Pace, number>> = {
  lose: { gradual: 0.25, moderate: 0.5, faster: 0.75 },
  gain: { gradual: 0.1, moderate: 0.25, faster: 0.5 },
};

export const GOAL_CHOICES: Choice[] = [
  { id: "lose_fat", label: "Lose body fat", description: "Reduce body fat while keeping muscle." },
  { id: "maintain", label: "Maintain weight", description: "Keep your weight about the same." },
  { id: "gain_muscle", label: "Gain muscle and strength", description: "Build muscle; some weight gain is expected." },
];

export const PACE_CHOICES: Choice[] = [
  { id: "gradual", label: "Gradual", description: "Smallest daily calorie change; easiest to sustain." },
  { id: "moderate", label: "Moderate", description: "A steady middle ground." },
  { id: "faster", label: "Faster", description: "Larger calorie change; still within Venn's safety limits." },
];

export const PROTEIN_CHOICES: (Choice & { gPerKg: number })[] = [
  { id: "standard", gPerKg: 1.6, label: "Flexible", description: "A lower, easier-to-maintain target." },
  { id: "high", gPerKg: 2.0, label: "Balanced", description: "Prioritise protein without building every meal around it." },
  { id: "very_high", gPerKg: 2.2, label: "High protein", description: "You're comfortable deliberately prioritising protein." },
];

export const ACTIVITY_CHOICES: Choice[] = [
  { id: "sedentary", label: "Mostly sitting", description: "Desk job, little walking." },
  { id: "light", label: "Lightly active", description: "Some walking or standing during the day." },
  { id: "moderate", label: "Active", description: "On your feet most of the day." },
  { id: "very", label: "Very active", description: "Physically demanding job or lots of daily walking." },
  { id: "extra", label: "Extremely active", description: "Hard physical work most of the day." },
];

export const EXPERIENCE_CHOICES: Choice[] = [
  { id: "beginner", label: "Beginner", description: "New or returning; less than a year of consistent training." },
  { id: "intermediate", label: "Intermediate", description: "1–3 years of consistent training." },
  { id: "advanced", label: "Advanced", description: "3+ years; comfortable with heavy compound lifts." },
];

export const TRAINING_GOAL_CHOICES: Choice[] = [
  { id: "build_muscle", label: "Build muscle" },
  { id: "get_stronger", label: "Get stronger" },
  { id: "muscular_endurance", label: "Muscular endurance" },
  { id: "cardio_fitness", label: "Cardio fitness" },
  { id: "general_fitness", label: "General fitness" },
  { id: "lose_fat", label: "Lose fat, keep muscle" },
];

export const SPLIT_CHOICES: Choice[] = [
  { id: "auto", label: "Let Venn choose", description: "Based on how many days you train." },
  { id: "full_body", label: "Full body" },
  { id: "upper_lower", label: "Upper / lower" },
  { id: "push_pull_legs", label: "Push / pull / legs" },
];

export const SEX_CHOICES: Choice[] = [
  { id: "female", label: "Female" }, { id: "male", label: "Male" },
  { id: "unspecified", label: "Prefer not to say", description: "Venn uses the midpoint of the two formulas." },
];

export const CARB_FAT_CHOICES: Choice[] = [
  { id: "balanced", label: "Balanced", description: "About 30% of calories from fat; the rest from carbs." },
  { id: "lower_carb", label: "More fat, fewer carbs", description: "About 40% of calories from fat." },
  { id: "lower_fat", label: "More carbs, less fat", description: "About 20% of calories from fat." },
];

export const EATING_PATTERNS: Choice[] = [
  { id: "vegetarian", label: "Vegetarian" }, { id: "vegan", label: "Vegan" }, { id: "pescatarian", label: "Pescatarian" },
  { id: "dairy_free", label: "Dairy-free" }, { id: "gluten_free", label: "Gluten-free" }, { id: "nut_free", label: "Nut-free" },
  { id: "halal", label: "Halal" }, { id: "kosher", label: "Kosher" },
];

// Workout duration ranges: the upper bound is stored as the session budget in minutes.
export const DURATION_CHOICES: Choice[] = [
  { id: "30", label: "15–30 minutes" }, { id: "45", label: "30–45 minutes" }, { id: "60", label: "45–60 minutes" },
  { id: "75", label: "60–75 minutes" }, { id: "90", label: "75–90 minutes" }, { id: "105", label: "90–105 minutes" },
  { id: "120", label: "105–120 minutes" }, { id: "custom", label: "More than 120 minutes" },
];
export const CUSTOM_DURATIONS = ["135", "150", "165", "180"];

export function durationLabel(minutes: string | number | null): string {
  const n = Number(minutes);
  if (!n) return "-";
  const range = DURATION_CHOICES.find((c) => c.id === String(n));
  if (range) return range.label;
  return n > 120 ? `${n} minutes (custom)` : `Up to ${n} minutes`;
}

export function durationChoiceId(minutes: string): string {
  if (!minutes) return "";
  if (Number(minutes) > 120) return "custom";
  return DURATION_CHOICES.some((c) => c.id === minutes) ? minutes : minutes; // non-standard values shown as "Up to N"
}

// Where people train. Presets only pre-select equipment; the final equipment list is what Venn uses.
export const GYM_LOCATIONS: (Choice & { equipment: string[] })[] = [
  { id: "commercial_gym", label: "Commercial gym", description: "A full-service gym with machines, free weights, and cardio equipment.",
    equipment: ["dumbbell", "barbell", "kettlebells", "cable", "machine", "bands", "e-z curl bar", "medicine ball", "exercise ball", "foam roll", "bench", "pull-up bar"] },
  { id: "strength_gym", label: "Strength gym", description: "A strength-focused facility with racks, barbells, plates, benches, and heavy free weights.",
    equipment: ["barbell", "dumbbell", "bench", "pull-up bar", "e-z curl bar", "kettlebells"] },
  { id: "local_gym", label: "Local gym", description: "A smaller gym with essential strength equipment and a more limited selection of machines.",
    equipment: ["dumbbell", "barbell", "bench", "cable", "machine", "pull-up bar"] },
  { id: "home_gym", label: "Home / garage gym", description: "A personal workout space with equipment such as dumbbells, a bench, or a rack.",
    equipment: ["dumbbell", "bench", "barbell", "pull-up bar", "bands"] },
  { id: "minimal", label: "Minimal equipment", description: "A small space with a few items, such as dumbbells or resistance bands.",
    equipment: ["dumbbell", "bands"] },
  { id: "bodyweight", label: "Bodyweight / outdoors", description: "Training at home, in a park, or outdoors, with little or no gym equipment.",
    equipment: [] },
];

export const CARDIO_SCHEDULE_CHOICES: Choice[] = [
  { id: "strength_days", label: "On my strength-training days", description: "Venn adds a cardio block to the end of your workouts." },
  { id: "separate_days", label: "On separate days", description: "Your strength workouts stay strength-only." },
  { id: "mix", label: "A mix of both", description: "Some cardio after strength workouts, some on other days." },
  { id: "none", label: "No cardio for now" },
];
export const CARDIO_MINUTES = ["10", "15", "20", "30", "45", "60"];

export const EATING_PATTERN_CHOICES: Choice[] = [
  { id: "none", label: "No specific restrictions" }, { id: "vegetarian", label: "Vegetarian" },
  { id: "vegan", label: "Vegan" }, { id: "pescatarian", label: "Pescatarian" }, { id: "other", label: "Other" },
];
// Dietary requirements (kept separate from eating patterns)
export const DIETARY_REQUIREMENTS: Choice[] = [
  { id: "dairy_free", label: "Dairy-free" }, { id: "gluten_free", label: "Gluten-free" }, { id: "nut_free", label: "Nut-free" },
  { id: "halal", label: "Halal" }, { id: "kosher", label: "Kosher" },
];
const PATTERN_IDS = ["vegetarian", "vegan", "pescatarian"];

export const ABILITY_EXERCISES: Choice[] = [
  { id: "pushups", label: "Push-ups" }, { id: "pullups", label: "Pull-ups or chin-ups" }, { id: "dips", label: "Dips" },
];
export const ABILITY_LEVELS: Choice[] = [
  { id: "none", label: "Can't do one yet" }, { id: "1_4", label: "1–4 reps" }, { id: "5_9", label: "5–9 reps" },
  { id: "10_14", label: "10–14 reps" }, { id: "15_plus", label: "15+ reps" }, { id: "unsure", label: "Not sure / haven't tried" },
];

/** g/kg shown as g/lb for imperial users; the stored multiplier is always per kg. */
export function proteinPerUnit(gPerKg: number, unit: "kg" | "lb"): string {
  return unit === "lb" ? `${(gPerKg * 0.45359237).toFixed(2)} g per lb` : `${gPerKg} g per kg`;
}

/** Everything the forms edit, in canonical units (cm, kg). */
export interface Model {
  sex: string; birth_year: string; height_cm: number | null; weight_kg: number | null;
  height_unit: HeightUnit; weight_unit: WeightUnit;
  activity_level: string; goalChoice: GoalChoice | ""; changeScale: boolean; pace: Pace;
  target_weight_kg: number | null; target_date: string; body_fat_pct: string;
  protein_level: string; diet_style: string; dietary_preferences: string[];
  training_goal: string; secondary_training_goal: string; experience: string;
  days_per_week: string; session_minutes: string; equipment: string[]; preferred_split: string;
  cardio_sessions_per_week: string; cardio_minutes: string; cardio_in_plan: boolean;
  gym_location: string; cardio_schedule: string; eating_pattern: string; eating_pattern_other: string;
  exercise_ability: Record<string, string>;
}

function nearestPace(goal: "lose" | "gain", rate: number): Pace {
  const entries = Object.entries(PACE_RATES[goal]) as [Pace, number][];
  return entries.reduce((best, cur) => (Math.abs(cur[1] - rate) < Math.abs(best[1] - rate) ? cur : best))[0];
}

export function fromProfile(p: Profile): Model {
  let goalChoice: GoalChoice | "" = "";
  let changeScale = true;
  if (p.goal_focus === "fat_loss" || (p.goal === "lose" && !p.goal_focus)) goalChoice = "lose_fat";
  else if (p.goal_focus === "recomp") { goalChoice = p.training_goal === "build_muscle" || p.training_goal === "get_stronger" ? "gain_muscle" : "lose_fat"; changeScale = false; }
  else if (p.goal_focus === "muscle_gain" || p.goal_focus === "lean_gain" || p.goal === "gain") goalChoice = "gain_muscle";
  else if (p.goal === "maintain") goalChoice = "maintain";
  const scaleGoal = p.goal === "lose" || p.goal === "gain" ? p.goal : null;
  return {
    sex: p.sex ?? "", birth_year: p.birth_year ? String(p.birth_year) : "",
    height_cm: p.height_cm, weight_kg: p.weight_kg,
    height_unit: (p.height_unit as HeightUnit) ?? "cm", weight_unit: (p.weight_unit as WeightUnit) ?? (p.units === "imperial" ? "lb" : "kg"),
    activity_level: p.activity_level ?? "", goalChoice, changeScale,
    pace: scaleGoal ? nearestPace(scaleGoal, p.goal_rate_pct ?? 0) : "moderate",
    target_weight_kg: p.target_weight_kg ?? null, target_date: p.target_date ?? "",
    body_fat_pct: p.body_fat_pct != null ? String(p.body_fat_pct) : "",
    protein_level: p.protein_level ?? "high", diet_style: p.diet_style ?? "balanced",
    dietary_preferences: p.dietary_preferences ?? [],
    training_goal: p.training_goal ?? "", secondary_training_goal: p.secondary_training_goal ?? "",
    experience: p.experience ?? "", days_per_week: p.days_per_week ? String(p.days_per_week) : "",
    session_minutes: p.session_minutes ? String(p.session_minutes) : "", equipment: p.equipment ?? [],
    preferred_split: p.preferred_split ?? "auto",
    cardio_sessions_per_week: String(p.cardio_sessions_per_week ?? 0), cardio_minutes: p.cardio_minutes ? String(p.cardio_minutes) : "",
    cardio_in_plan: p.cardio_in_plan ?? false,
    gym_location: p.gym_location ?? "",
    cardio_schedule: p.cardio_schedule ?? (p.cardio_sessions_per_week ? (p.cardio_in_plan ? "strength_days" : "separate_days") : ""),
    eating_pattern: p.eating_pattern ?? ((p.dietary_preferences ?? []).find((d) => PATTERN_IDS.includes(d)) ?? ""),
    eating_pattern_other: p.eating_pattern_other ?? "",
    exercise_ability: p.exercise_ability ?? {},
  };
}

/** The calculator inputs implied by the goal answers. */
export function goalFields(m: Model): { goal: "lose" | "maintain" | "gain"; goal_rate_pct: number; goal_focus: string } {
  if (m.goalChoice === "lose_fat") {
    return m.changeScale ? { goal: "lose", goal_rate_pct: PACE_RATES.lose[m.pace], goal_focus: "fat_loss" }
      : { goal: "maintain", goal_rate_pct: 0, goal_focus: "recomp" };
  }
  if (m.goalChoice === "gain_muscle") {
    return m.changeScale ? { goal: "gain", goal_rate_pct: PACE_RATES.gain[m.pace], goal_focus: "muscle_gain" }
      : { goal: "maintain", goal_rate_pct: 0, goal_focus: "recomp" };
  }
  return { goal: "maintain", goal_rate_pct: 0, goal_focus: "maintain" };
}

export function hasScaleGoal(m: Model): boolean {
  return m.goalChoice !== "maintain" && m.goalChoice !== "" && m.changeScale;
}

export function toInput(m: Model): ProfileInput {
  const g = goalFields(m);
  const scale = g.goal !== "maintain";
  return {
    sex: m.sex as ProfileInput["sex"], birth_year: Number(m.birth_year),
    height_cm: Math.round((m.height_cm ?? 0) * 100) / 100, weight_kg: Math.round((m.weight_kg ?? 0) * 1000) / 1000,
    height_unit: m.height_unit, weight_unit: m.weight_unit,
    activity_level: m.activity_level as ProfileInput["activity_level"], goal: g.goal, goal_rate_pct: g.goal_rate_pct,
    goal_focus: g.goal_focus,
    target_weight_kg: scale && m.target_weight_kg != null ? Math.round(m.target_weight_kg * 1000) / 1000 : null,
    target_date: scale && m.target_weight_kg != null && m.target_date ? m.target_date : null,
    body_fat_pct: m.body_fat_pct === "" ? null : Number(m.body_fat_pct),
    protein_level: m.protein_level as ProfileInput["protein_level"], diet_style: m.diet_style as ProfileInput["diet_style"],
    // dietary_preferences keeps requirements plus the pattern (for older readers); eating_pattern is the source of truth
    dietary_preferences: [
      ...m.dietary_preferences.filter((d) => !PATTERN_IDS.includes(d)),
      ...(PATTERN_IDS.includes(m.eating_pattern) ? [m.eating_pattern] : []),
    ],
    eating_pattern: m.eating_pattern || null,
    eating_pattern_other: m.eating_pattern === "other" && m.eating_pattern_other.trim() ? m.eating_pattern_other.trim() : null,
    gym_location: m.gym_location || null,
    exercise_ability: Object.keys(m.exercise_ability).length ? m.exercise_ability : null,
    training_goal: m.training_goal as ProfileInput["training_goal"],
    secondary_training_goal: m.secondary_training_goal ? (m.secondary_training_goal as ProfileInput["training_goal"]) : null,
    experience: m.experience as ProfileInput["experience"], days_per_week: Number(m.days_per_week),
    session_minutes: Number(m.session_minutes), equipment: m.equipment,
    preferred_split: m.preferred_split as ProfileInput["preferred_split"],
    cardio_schedule: m.cardio_schedule || null,
    cardio_sessions_per_week: m.cardio_schedule === "none" ? 0 : Number(m.cardio_sessions_per_week || 0),
    cardio_minutes: m.cardio_schedule === "none" || m.cardio_minutes === "" ? null : Number(m.cardio_minutes),
    cardio_in_plan: m.cardio_schedule ? m.cardio_schedule === "strength_days" || m.cardio_schedule === "mix"
      : Number(m.cardio_sessions_per_week || 0) > 0 && m.cardio_in_plan,
  };
}

/** The body weight protein is based on: current weight, or the target weight when deliberately losing
 *  scale weight with a lower target set (mirrors backend targets.protein_reference). */
export function proteinReferenceKg(m: Pick<Model, "weight_kg" | "target_weight_kg"> & { losing: boolean }): number | null {
  if (!m.weight_kg) return null;
  if (m.losing && m.target_weight_kg && m.target_weight_kg >= 35 && m.target_weight_kg < m.weight_kg) return m.target_weight_kg;
  return m.weight_kg;
}

/** Daily protein implied by a preference (before the calculator's 35%-of-calories cap). */
export function proteinGrams(weightKg: number | null, level: string): number | null {
  const c = PROTEIN_CHOICES.find((p) => p.id === level);
  return weightKg && c ? Math.round(weightKg * c.gPerKg) : null;
}

export function emptyModel(): Model {
  return fromProfile({
    sex: null, birth_year: null, height_cm: null, weight_kg: null, activity_level: null, goal: null, goal_rate_pct: 0,
    protein_level: "high", diet_style: "balanced", dietary_preferences: [], training_goal: null, experience: null,
    days_per_week: null, session_minutes: null, equipment: [], preferred_split: "auto", units: "metric", is_complete: false,
  } as unknown as Profile);
}
