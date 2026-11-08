/**
 * Bar chart spec — the JSON contract between the AI backend and the UI.
 *
 * Everything in `BarChartSpec` is plain, serialisable JSON so a model can emit it
 * directly as a tool call. Keep this file in sync with `bar-chart.schema.json`.
 */

/** Categorical colours, validated for colour-blind separation on the dark surface. */
export type SeriesColor = "purple" | "teal" | "orange" | "blue" | "neutral";

export type Orientation = "vertical" | "horizontal";

/** grouped = side by side · stacked = summed · percent = stacked, each category scaled to 100%. */
export type BarLayout = "grouped" | "stacked" | "percent";

/**
 * Which bars get a printed value. Tooltips and the table always carry every value.
 * auto: stacked → totals, single series → max, grouped → none.
 */
export type ValueLabels = "auto" | "none" | "all" | "max" | "min-max" | "last" | "totals";

export type SortOrder = "none" | "asc" | "desc";

export interface ValueFormat {
  /** number (default) · currency · percent (values are already percentages: 45 → "45%"). */
  style?: "number" | "currency" | "percent";
  /** ISO 4217 code, used when style is "currency". Default "USD". */
  currency?: string;
  /** Fixed number of decimals. Default: up to 2 (0 for currency when compact). */
  decimals?: number;
  /** Compact notation (12.4K, $1.2M). "auto" (default) compacts once values reach 10,000. */
  compact?: boolean | "auto";
  prefix?: string;
  suffix?: string;
}

export interface BarSeries {
  name: string;
  /** One value per category, in the same order as `categories`. null = no data. */
  values: (number | null)[];
  /** Pin a colour so an entity keeps it across charts. Defaults to palette order. */
  color?: SeriesColor;
}

export interface AxisOptions {
  label?: string;
  show?: boolean;
}

export interface ValueAxisOptions extends AxisOptions {
  /** Must be ≤ 0 — bars always grow from zero. */
  min?: number;
  /** Must be ≥ 0. */
  max?: number;
  /** Approximate number of ticks. Default 5. */
  tickCount?: number;
  gridlines?: boolean;
}

export interface ReferenceLine {
  value: number;
  label?: string;
}

export interface BarChartSpec {
  title?: string;
  subtitle?: string;
  categories: string[];
  series: BarSeries[];
  orientation?: Orientation;
  layout?: BarLayout;
  valueFormat?: ValueFormat;
  /** The axis the categories sit on. */
  categoryAxis?: AxisOptions;
  /** The axis the values are measured on. */
  valueAxis?: ValueAxisOptions;
  valueLabels?: ValueLabels;
  /** Legend shows automatically for 2+ series. */
  legend?: { show?: boolean };
  /** Categories to emphasise; the others are dimmed. */
  highlight?: string[];
  /** Horizontal/vertical rules at a value, e.g. a budget or target. */
  referenceLines?: ReferenceLine[];
  /** Sort categories by total value. */
  sort?: SortOrder;
  /** Chart height in px for vertical charts (default 320). Horizontal charts size to their rows. */
  height?: number;
  /** Shown when there is nothing to plot. */
  emptyMessage?: string;
}

/** The spec after normalisation: every field resolved, safe to render. */
export interface ResolvedBarChartSpec
  extends Required<Omit<BarChartSpec, "title" | "subtitle" | "series" | "valueFormat" | "categoryAxis" | "valueAxis" | "legend">> {
  title?: string;
  subtitle?: string;
  series: Required<BarSeries>[];
  valueFormat: ValueFormat;
  categoryAxis: Required<Pick<AxisOptions, "show">> & AxisOptions;
  valueAxis: Required<Pick<ValueAxisOptions, "show" | "gridlines" | "tickCount">> & ValueAxisOptions;
  legend: { show: boolean };
}

export interface NormalizeResult {
  spec: ResolvedBarChartSpec;
  /** Everything that was coerced or dropped — log it or return it to the model. */
  warnings: string[];
}
