/** Types shared by every AI-driven chart spec. Plain JSON only. */

/** Categorical colours, validated for colour-blind separation on the dark surface. */
export type SeriesColor = "purple" | "teal" | "orange" | "blue" | "neutral";

export interface ValueFormat {
  /** number (default) · currency · percent (values are already percentages: 45 → "45%"). */
  style?: "number" | "currency" | "percent";
  /** ISO 4217 code, used when style is "currency". Default "USD". */
  currency?: string;
  /** Fixed number of decimals. Default: whole numbers bare, fractions up to 2. */
  decimals?: number;
  /** Compact notation (12.4K, $1.2M). "auto" (default) compacts once values reach 10,000. */
  compact?: boolean | "auto";
  prefix?: string;
  suffix?: string;
}

export interface ReferenceLine {
  value: number;
  label?: string;
}

export interface AxisOptions {
  label?: string;
  show?: boolean;
}

export interface LinearAxisOptions extends AxisOptions {
  min?: number;
  max?: number;
  /** Approximate number of ticks. Default 5. */
  tickCount?: number;
  gridlines?: boolean;
}

/** Every chart's normaliser returns this shape. */
export interface Normalized<T> {
  spec: T;
  /** Everything that was coerced or dropped — log it or return it to the model. */
  warnings: string[];
}
