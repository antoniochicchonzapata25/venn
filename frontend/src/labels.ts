// Human-readable labels for API enum values, and unit conversion helpers.

export const LABELS: Record<string, Record<string, string>> = {
  sex: { male: "Male", female: "Female", unspecified: "Prefer not to say" },
  activity_level: {
    sedentary: "Sedentary (desk job, little exercise)",
    light: "Lightly active (1-3 workouts/week)",
    moderate: "Moderately active (3-5 workouts/week)",
    very: "Very active (6-7 workouts/week)",
    extra: "Extremely active (physical job + training)",
  },
  goal: { lose: "Lose body fat", maintain: "Maintain weight", gain: "Gain muscle and strength" },
  protein_level: { standard: "Flexible (1.6 g/kg)", high: "Balanced (2.0 g/kg)", very_high: "High protein (2.2 g/kg)" },
  diet_style: { balanced: "balanced carb/fat split (about 30% of calories from fat)", lower_carb: "more fat, fewer carbs (about 40% of calories from fat)", lower_fat: "more carbs, less fat (about 20% of calories from fat)" },
  training_goal: {
    build_muscle: "Build muscle", get_stronger: "Get stronger", muscular_endurance: "Muscular endurance",
    cardio_fitness: "Cardio fitness", general_fitness: "General fitness", lose_fat: "Lose fat, keep muscle",
  },
  experience: { beginner: "Beginner (< 1 year)", intermediate: "Intermediate (1-3 years)", advanced: "Advanced (3+ years)" },
  preferred_split: {
    auto: "Let Venn choose", full_body: "Full body", upper_lower: "Upper / lower", push_pull_legs: "Push / pull / legs",
  },
  units: { metric: "Metric (kg, cm)", imperial: "Imperial (lb, in)" },
  body_area: {
    neck: "Neck", shoulder: "Shoulder", elbow: "Elbow", wrist_hand: "Wrist / hand", upper_back: "Upper back",
    lower_back: "Lower back", hip: "Hip", knee: "Knee", ankle_foot: "Ankle / foot", other: "Other",
  },
  kind: { temporary: "Temporary", ongoing: "Ongoing" },
  severity: { avoid: "Avoid loading this area", caution: "Train with caution" },
  dietary_preferences: {
    vegetarian: "Vegetarian", vegan: "Vegan", pescatarian: "Pescatarian", dairy_free: "Dairy-free",
    gluten_free: "Gluten-free", nut_free: "Nut-free", halal: "Halal", kosher: "Kosher",
  },
};

export const label = (group: string, value: string | null | undefined): string =>
  value == null ? "-" : LABELS[group]?.[value] ?? value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export const MAX_RATE: Record<string, number> = { lose: 1.0, maintain: 0, gain: 0.5 };

export const KG_PER_LB = 0.45359237;
export const CM_PER_IN = 2.54;
export const round1 = (n: number) => Math.round(n * 10) / 10;
