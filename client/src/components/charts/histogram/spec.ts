import {
  clamp,
  isObject,
  normalizeFormat,
  normalizeLinearAxis,
  normalizeReferenceLines,
  optionalNumber,
  optionalString,
  pickColor,
  toArray,
  toNumber,
} from "../shared/coerce";
import type { ResolvedLinearAxis } from "../shared/coerce";
import { niceStep } from "../shared/scale";
import type { AxisOptions, LinearAxisOptions, Normalized, ReferenceLine, SeriesColor, ValueFormat } from "../shared/types";

/**
 * Histogram spec — the distribution of one measure.
 * Send raw `values` (binned here) or pre-computed `bins`.
 * Keep in sync with `histogram.schema.json`.
 */

export type Marker = "mean" | "median";

export interface HistogramBin {
  start: number;
  end: number;
  count: number;
}

export interface HistogramSpec {
  title?: string;
  subtitle?: string;
  /** Raw observations, e.g. every transaction amount. */
  values?: number[];
  /** Pre-binned data. Used instead of `values` when given. */
  bins?: HistogramBin[];
  /** Approximate number of bins (rounded to a clean width). Default: chosen from the data. */
  binCount?: number;
  /** Exact bin width; overrides binCount. */
  binWidth?: number;
  /** Formats the measured value (x axis). */
  valueFormat?: ValueFormat;
  /** What a count means, e.g. "Transactions". Default "Count". */
  countLabel?: string;
  /** Draw summary rules. Only available with raw `values`. */
  markers?: Marker[];
  /** Extra vertical rules on the value axis. */
  referenceLines?: ReferenceLine[];
  /** Emphasise bins inside this range; others are dimmed. */
  highlightRange?: { from?: number; to?: number };
  color?: SeriesColor;
  xAxis?: AxisOptions;
  yAxis?: Omit<LinearAxisOptions, "min">;
  height?: number;
  emptyMessage?: string;
}

export interface ResolvedHistogramSpec {
  title?: string;
  subtitle?: string;
  bins: HistogramBin[];
  total: number;
  /** Present only when raw values were provided. */
  stats?: { mean: number; median: number; min: number; max: number; n: number };
  valueFormat: ValueFormat;
  countLabel: string;
  markers: Marker[];
  referenceLines: ReferenceLine[];
  highlightRange?: { from: number; to: number };
  color: SeriesColor;
  xAxis: { label?: string; show: boolean };
  yAxis: ResolvedLinearAxis;
  height: number;
  emptyMessage: string;
}

export function normalizeHistogramSpec(input: unknown): Normalized<ResolvedHistogramSpec> {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");

  let bins: HistogramBin[] = [];
  let stats: ResolvedHistogramSpec["stats"];

  if (Array.isArray(raw.bins) && raw.bins.length) {
    bins = raw.bins.flatMap((b, i) => {
      if (!isObject(b)) return [];
      const start = toNumber(b.start ?? b.from, `bins[${i}].start`, warnings);
      const end = toNumber(b.end ?? b.to, `bins[${i}].end`, warnings);
      const count = toNumber(b.count, `bins[${i}].count`, warnings);
      if (start === null || end === null || count === null || end <= start) {
        warnings.push(`bins[${i}] needs start < end and a count; dropped.`);
        return [];
      }
      return [{ start, end, count: Math.max(0, count) }];
    });
    bins.sort((a, b) => a.start - b.start);
    if (Array.isArray(raw.values)) warnings.push("Both bins and values were given; using bins.");
  } else {
    const values = toArray(raw.values)
      .map((v, i) => toNumber(v, `values[${i}]`, warnings))
      .filter((v): v is number => v !== null);
    if (values.length) {
      const sorted = [...values].sort((a, b) => a - b);
      const n = sorted.length;
      const q = (p: number) => {
        const idx = (n - 1) * p;
        const lo = Math.floor(idx);
        return sorted[lo] + (sorted[Math.min(n - 1, lo + 1)] - sorted[lo]) * (idx - lo);
      };
      stats = { n, min: sorted[0], max: sorted[n - 1], mean: values.reduce((a, b) => a + b, 0) / n, median: q(0.5) };

      // Bin width: explicit, else from binCount, else Freedman–Diaconis (clamped to 5–40 bins).
      const span = stats.max - stats.min || Math.abs(stats.max) || 1;
      let width = optionalNumber(raw.binWidth);
      if (width !== undefined && (width <= 0 || span / width > 200)) {
        warnings.push("binWidth is out of range; choosing one automatically.");
        width = undefined;
      }
      if (width === undefined) {
        const requested = optionalNumber(raw.binCount);
        const iqr = q(0.75) - q(0.25);
        const fd = iqr > 0 ? span / ((2 * iqr) / Math.cbrt(n)) : Math.log2(n) + 1;
        const count = clamp(Math.round(requested ?? fd), 1, requested ? 100 : 40);
        width = niceStep(span / count);
      }
      const start = Math.floor(stats.min / width) * width;
      const binN = Math.max(1, Math.ceil((stats.max - start) / width + 1e-9));
      bins = Array.from({ length: binN }, (_, i) => ({
        start: Number((start + i * width!).toPrecision(12)),
        end: Number((start + (i + 1) * width!).toPrecision(12)),
        count: 0,
      }));
      for (const v of values) {
        const i = Math.min(binN - 1, Math.floor((v - start) / width + 1e-9));
        bins[i].count++;
      }
    } else if (isObject(input)) {
      warnings.push("Spec has no `values` or `bins`; rendering an empty chart.");
    }
  }

  const markers = toArray(raw.markers).filter((m): m is "mean" | "median" => m === "mean" || m === "median");
  if (markers.length && !stats) warnings.push("markers need raw `values`; ignored for pre-binned data.");

  const hr = isObject(raw.highlightRange) ? raw.highlightRange : undefined;
  const xAxisRaw = isObject(raw.xAxis) ? raw.xAxis : {};

  return {
    warnings,
    spec: {
      title: optionalString(raw.title),
      subtitle: optionalString(raw.subtitle),
      bins,
      total: bins.reduce((a, b) => a + b.count, 0),
      stats,
      valueFormat: normalizeFormat(raw.valueFormat),
      countLabel: optionalString(raw.countLabel) ?? "Count",
      markers: stats ? [...new Set(markers)] : [],
      referenceLines: normalizeReferenceLines(raw.referenceLines, warnings),
      highlightRange: hr ? { from: optionalNumber(hr.from) ?? -Infinity, to: optionalNumber(hr.to) ?? Infinity } : undefined,
      color: pickColor(raw.color, "color", warnings) ?? "purple",
      xAxis: { label: optionalString(xAxisRaw.label), show: xAxisRaw.show !== false },
      yAxis: normalizeLinearAxis(raw.yAxis),
      height: clamp(optionalNumber(raw.height) ?? 280, 160, 800),
      emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
    },
  };
}
