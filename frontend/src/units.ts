// Display-unit conversions. Values are always stored in metric (cm, kg); these only format and parse.
export const CM_PER_INCH = 2.54;
export const KG_PER_LB = 0.45359237;

export type HeightUnit = "cm" | "ft_in";
export type WeightUnit = "kg" | "lb";

export function cmToFtIn(cm: number): { ft: number; inches: number } {
  const totalIn = cm / CM_PER_INCH;
  let ft = Math.floor(totalIn / 12);
  let inches = Math.round((totalIn - ft * 12) * 10) / 10;
  if (inches >= 12) { ft += 1; inches = 0; }
  return { ft, inches };
}

export const ftInToCm = (ft: number, inches: number) => (ft * 12 + inches) * CM_PER_INCH;
export const kgToLb = (kg: number) => kg / KG_PER_LB;
export const lbToKg = (lb: number) => lb * KG_PER_LB;
export const round1 = (n: number) => Math.round(n * 10) / 10;

/** Text shown in a weight input for a stored kg value. */
export function weightText(kg: number | null, unit: WeightUnit): string {
  if (kg == null || !Number.isFinite(kg)) return "";
  return String(round1(unit === "lb" ? kgToLb(kg) : kg));
}

/** Parse a weight input back to kg (full precision; no re-rounding, so switching units never drifts). */
export function parseWeight(text: string, unit: WeightUnit): number | null {
  if (text.trim() === "") return null;
  const n = Number(text);
  if (!Number.isFinite(n)) return null;
  return unit === "lb" ? lbToKg(n) : n;
}

export function formatWeight(kg: number | null, unit: WeightUnit): string {
  return kg == null ? "-" : `${weightText(kg, unit)} ${unit}`;
}

export function formatHeight(cm: number | null, unit: HeightUnit): string {
  if (cm == null) return "-";
  if (unit === "cm") return `${round1(cm)} cm`;
  const { ft, inches } = cmToFtIn(cm);
  return `${ft} ft ${inches} in`;
}
