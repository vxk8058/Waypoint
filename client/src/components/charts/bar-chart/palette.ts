import type { SeriesColor } from "./types";

/**
 * Validated against the dark surface (#0A1628): every slot sits in the OKLCH
 * lightness band, adjacent pairs clear ΔE 8 under protan/deutan/tritan simulation,
 * and all clear 3:1 contrast. Change the order or steps only after re-validating.
 * Red is deliberately absent — it is reserved for status (over budget, errors).
 */
export const SERIES_COLORS: Record<SeriesColor, { fill: string; hex: string }> = {
  purple: { fill: "var(--color-purple-400)", hex: "#7069FA" },
  teal: { fill: "var(--color-teal-500)", hex: "#27AB83" },
  orange: { fill: "var(--color-yellow-vivid-700)", hex: "#CB6E17" },
  blue: { fill: "var(--color-light-blue-vivid-600)", hex: "#1992D4" },
  neutral: { fill: "var(--color-blue-grey-500)", hex: "#627D98" },
};

/** Fixed assignment order — never cycled. */
export const CATEGORICAL_ORDER: SeriesColor[] = ["purple", "teal", "orange", "blue"];
export const MAX_COLORED_SERIES = CATEGORICAL_ORDER.length;

export const CHART_TOKENS = {
  textPrimary: "var(--color-blue-grey-050)",
  textSecondary: "var(--color-blue-grey-300)",
  textMuted: "var(--color-blue-grey-500)",
  grid: "var(--color-blue-grey-800)",
  baseline: "var(--color-blue-grey-600)",
  reference: "var(--color-blue-grey-300)",
  hoverWash: "var(--color-surface-raised)",
};

/** White or near-black for a label printed inside a fill. */
export function inkOn(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.22 ? "#010614" : "#FFFFFF";
}
