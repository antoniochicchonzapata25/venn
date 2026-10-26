export interface User {
  id: number;
  username: string;
  display_name: string;
}

export type Sex = "male" | "female" | "unspecified";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "very" | "extra";
export type Goal = "lose" | "maintain" | "gain";
export type ProteinLevel = "standard" | "high" | "very_high";
export type DietStyle = "balanced" | "lower_carb" | "lower_fat";
export type TrainingGoal =
  | "build_muscle" | "get_stronger" | "muscular_endurance" | "cardio_fitness" | "general_fitness" | "lose_fat";
export type Experience = "beginner" | "intermediate" | "advanced";
export type Split = "auto" | "full_body" | "upper_lower" | "push_pull_legs";
export type Units = "metric" | "imperial";

export interface ProfileInput {
  sex: Sex;
  birth_year: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  goal: Goal;
  goal_rate_pct: number;
  protein_level: ProteinLevel;
  diet_style: DietStyle;
  dietary_preferences: string[];
  training_goal: TrainingGoal;
  experience: Experience;
  days_per_week: number;
  session_minutes: number;
  equipment: string[];
  preferred_split: Split;
  units?: Units;
  // Milestone 3.5 (optional)
  height_unit?: "cm" | "ft_in";
  weight_unit?: "kg" | "lb";
  goal_focus?: string | null;
  target_weight_kg?: number | null;
  target_date?: string | null;
  body_fat_pct?: number | null;
  secondary_training_goal?: TrainingGoal | null;
  cardio_sessions_per_week?: number;
  cardio_minutes?: number | null;
  cardio_in_plan?: boolean;
  gym_location?: string | null;
  cardio_schedule?: string | null;
  eating_pattern?: string | null;
  eating_pattern_other?: string | null;
  exercise_ability?: Record<string, string> | null;
}

export interface GoalProjection {
  target_weight_kg: number;
  change_kg: number;
  weeks_at_pace?: number;
  estimated_date?: string;
  weekly_change_kg?: number;
  required_rate_pct?: number;
  date_check?: string;
}

export type Profile = { [K in keyof ProfileInput]: ProfileInput[K] | null } & {
  is_complete: boolean;
  goal_projection?: GoalProjection | null;
};

export interface TargetBreakdown {
  bmr?: number;
  activity_multiplier?: number;
  tdee?: number;
  daily_energy_change?: number;
  unrounded_kcal?: number;
  minimum_kcal?: number;
  minimum_applied?: boolean;
  protein_capped?: boolean;
  estimated_weekly_change_kg?: number;
  warnings?: string[];
  source?: string;
}

export interface Target {
  id: number;
  method: "formula" | "manual";
  kcal: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
  breakdown: TargetBreakdown;
  created_at: string;
}

export interface Limitation {
  id: number;
  body_area: string;
  kind: "temporary" | "ongoing";
  severity: "avoid" | "caution";
  note: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Options {
  equipment: string[];
  dietary_preferences: string[];
  disclaimer: string;
}

export interface AiStatus {
  configured: boolean;
  model: string;
  provider: string;
  message: string | null;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  database: string;
  ai: AiStatus;
}

// ---------------------------------------------------------------- nutrition (Milestone 2)

export interface Macros {
  kcal: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
}

export type NutrientKey = keyof Macros;

export interface UnitOption {
  unit: string;
  label: string;
  size: number;
  kind: "mass" | "volume" | "count";
}

export interface FoodSummary {
  id: number;
  name: string;
  brand: string;
  category: string;
  source: string;
  source_label: string;
  barcode: string | null;
  basis: "g" | "ml";
  per_100: Macros;
  default_unit: { unit: string; label: string; size: number; nutrition: Macros };
}

export interface FoodDetail extends FoodSummary {
  source_ref: string;
  published: string;
  serving_size: number | null;
  serving_label: string;
  units: UnitOption[];
}

export interface RecentFood extends FoodSummary {
  times_logged: number;
  last: { quantity: number; unit: string; unit_label: string; kcal: number; eaten_at: string };
}

export interface FoodEntry extends Macros {
  id: number;
  food_id: number | null;
  kind: "catalog" | "manual";
  description: string;
  brand: string;
  quantity: number;
  unit: string;
  unit_label: string;
  amount: number | null;
  basis: "g" | "ml" | null;
  eaten_at: string; // local wall-clock "YYYY-MM-DDTHH:MM"
  local_date: string;
  units: UnitOption[];
  source_label: string;
}

export interface Progress {
  consumed: number;
  target: number | null;
  remaining: number | null;
  over: number | null;
  percent: number | null;
  state: "no_target" | "empty" | "partial" | "met" | "over";
}

export interface DaySummary {
  date: string;
  entries: FoodEntry[];
  totals: Macros;
  target: (Macros & { id: number; method: string }) | null;
  progress: Record<NutrientKey, Progress>;
  protein_range?: ProteinRange | null;
}

export interface ProteinRange {
  low: number;
  high: number;
  nominal: number;
  eaten: number;
  state: "below" | "within" | "above";
  to_low: number;
  above_high: number;
}

export interface WeekSummary {
  start: string;
  end: string;
  days: { date: string; entries: number; kcal: number }[];
  days_logged: number;
}

export interface ConfirmationNeeded {
  code: "confirmation_required";
  warnings: string[];
  suggestions: { quantity: number; unit: string; label: string }[];
  preview: Macros & { amount?: number | null };
}

export interface AiCheck extends AiStatus {
  status: "ok" | "error" | "disabled";
  served_model?: string | null;
  latency_ms?: number;
  usage?: { input_tokens: number; cached_input_tokens: number; output_tokens: number; reasoning_tokens: number };
  cached: boolean;
}

// ---------------------------------------------------------------- training (Milestone 3)

export interface WorkoutSet {
  id: number;
  set_index: number;
  reps: number | null;
  weight_kg: number | null;
  weight_lb: number | null;
  duration_seconds: number | null;
  logged_at: string;
}

export interface WorkoutExercise {
  id: number;
  position: number;
  exercise_id: string;
  name: string;
  pattern: string;
  role: "main" | "accessory";
  measure: "reps" | "time";
  target_sets: number;
  rep_low: number | null;
  rep_high: number | null;
  target_seconds: number | null;
  rest_seconds: number;
  est_minutes: number;
  instructions: string[];
  notes: string[];
  suggested_weight_kg: number | null;
  suggested_weight_lb: number | null;
  last_summary: string | null;
  replaced_exercise_id: string | null;
  completed: boolean;
  equipment: string[];
  sets: WorkoutSet[];
}

export interface WorkoutSummaryStats {
  planned_minutes: number;
  actual_minutes: number | null;
  difference_minutes: number | null;
  sets_logged: number;
  sets_planned: number;
  exercises_completed: number;
  exercises_planned: number;
  volume_kg: number;
  records: { exercise: string; weight_kg: number; previous_kg: number }[];
}

export interface WorkoutBrief {
  id: number;
  status: "planned" | "in_progress" | "completed" | "discarded";
  name: string;
  split: string;
  day_type: string;
  goal: string;
  objective: string;
  generator: string;
  budget_minutes: number;
  planned_minutes: number;
  is_demo: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  summary: WorkoutSummaryStats | null;
}

export interface Workout extends WorkoutBrief {
  explanation: string[];
  exercises: WorkoutExercise[];
  exercise_source: string;
  warnings?: string[];
}

export interface TrainingOptions {
  split: string;
  split_reason: string;
  day_types: { id: string; name: string }[];
  all_day_types: { id: string; name: string }[];
  next_day_type: string;
  session_minutes: number;
  units: "kg" | "lb";
  preferred_split: string;
  splits: { id: string; name: string }[];
}

export interface TrainingSummary {
  planned: WorkoutBrief | null;
  in_progress: WorkoutBrief | null;
  completed_last_7_days: number;
  days_per_week: number | null;
  history: WorkoutBrief[];
  average_difference_minutes: number | null;
  sessions_compared: number;
}

export interface Alternative {
  id: string;
  name: string;
  pattern: string;
  pattern_label: string;
  equipment: string[];
  level: string;
  primary_muscles: string[];
  reason: string;
  notes: string[];
}

// ---------------------------------------------------------------- AI Coach (Milestone 4)

export interface CoachChecks {
  numbers_checked?: number;
  numbers_verified?: number;
  unverified_numbers?: number[];
  grounded?: boolean;
  untrusted_text_flags?: string[];
  exercises_mentioned?: string[];
  exercise_conflicts?: { exercise: string; reasons: string[] }[];
}

export interface CoachRun {
  id: number;
  question: string;
  workflow: string;
  routed_by: string;
  status: "ok" | "error" | "limit";
  answer: string | null;
  error: string | null;
  model: string;
  model_calls: number;
  tool_calls: number;
  usage: { input_tokens: number; cached_input_tokens: number; output_tokens: number; reasoning_tokens: number; complete: boolean };
  estimated_cost_usd: number;
  latency_ms: number;
  checks: CoachChecks;
  tools_used: string[];
  created_at: string | null;
  price_source: string;
  trace?: Record<string, unknown>[];
}

export interface CoachStatus { enabled: boolean; model: string; runs_today: number; daily_limit: number; message: string | null }

export interface CoachMetrics {
  window_days: number;
  nutrition: Record<string, number | null>;
  training: Record<string, number | null>;
  body_measurements: string;
}

// ---------------------------------------------------------------- Body (Milestone 5)
export interface WeightEntry { id: number; entry_date: string; weight_kg: number }
export interface WeightHistory {
  entries: WeightEntry[]; latest: WeightEntry | null; previous: WeightEntry | null;
  change_kg: number | null; days_between: number | null; note: string; replaced?: boolean;
}
export type MeasurementField = "waist" | "chest" | "hips" | "biceps" | "thigh";
export type MeasurementEntry = { id: number; entry_date: string } & Record<`${MeasurementField}_cm`, number | null>;
export interface MeasurementComparison {
  latest_cm: number | null; latest_date: string | null; previous_cm: number | null; previous_date: string | null; change_cm: number | null;
}
export interface MeasurementHistory {
  entries: MeasurementEntry[]; comparison: Record<MeasurementField, MeasurementComparison>; fields: MeasurementField[];
  note: string; replaced?: boolean;
}
export type RecoveryState = "none" | "low" | "moderate" | "high";
export type MuscleGroupId = "back" | "biceps" | "chest" | "shoulders" | "triceps" | "lower_back" | "abs" | "glutes" | "hamstrings" | "quadriceps";
export interface RecoveryGroup {
  id: MuscleGroupId; label: string; state: RecoveryState; state_label: string; residual: number; weighted_sets_7d: number;
  last_workout: { id: number; name: string; finished_at: string; hours_ago: number; is_demo: boolean; local_date: string } | null;
  exercises: { name: string; sets: number; role: "primary" | "secondary"; weighted_sets: number }[];
}
export interface Recovery {
  has_history: boolean;
  last_workout: { id: number; name: string; finished_at: string; is_demo: boolean; local_date: string; days_since: number; groups_trained: number } | null;
  counts: Record<RecoveryState, number>;
  groups: RecoveryGroup[];
  model: { window_days: number; decay_hours: number; moderate_at: number; high_at: number; explanation: string; disclaimer: string; states: Record<RecoveryState, string> };
  soreness: Partial<Record<MuscleGroupId, { rating: number; recorded_at: string }>>;
}
