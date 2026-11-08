import {
  assignColors,
  clamp,
  isObject,
  looksLikeDate,
  normalizeFormat,
  normalizeLinearAxis,
  normalizeReferenceLines,
  optionalNumber,
  optionalString,
  pickBool,
  pickColor,
  pickEnum,
  toArray,
  toDate,
  toNumber,
  uniqueNames,
} from "../shared/coerce";
import type { ResolvedLinearAxis } from "../shared/coerce";
import { MAX_COLORED_SERIES } from "../shared/palette";
import type { AxisOptions, LinearAxisOptions, Normalized, ReferenceLine, SeriesColor, ValueFormat } from "../shared/types";

/**
 * Line chart spec — trends over time or any ordered x.
 * Keep in sync with `line-chart.schema.json`.
 */

export type XType = "time" | "number" | "category";
export type Curve = "linear" | "monotone" | "step";
export type Markers = "auto" | "none" | "last" | "all";
export type LineValueLabels = "auto" | "none" | "last" | "max" | "min-max";

export interface LineSeries {
  name: string;
  /** One value per x, same order as `x`. null breaks the line. */
  values: (number | null)[];
  color?: SeriesColor;
  /** Optional uncertainty band (e.g. simulation 10th–90th percentile). */
  band?: { lower: (number | null)[]; upper: (number | null)[] };
}

export interface LineChartSpec {
  title?: string;
  subtitle?: string;
  /** X values: ISO dates ("2026-03-01"), numbers, or category labels. */
  x: (string | number)[];
  /** Override x type detection. */
  xType?: XType;
  series: LineSeries[];
  curve?: Curve;
  /** Fill a light wash under each line. Best with a single series. */
  area?: boolean;
  markers?: Markers;
  valueLabels?: LineValueLabels;
  /** Series name printed at the end of each line (default: on for 2–4 series when they don't collide). */
  endLabels?: boolean;
  /** Series to emphasise; the rest turn grey. */
  highlight?: string[];
  /** X value where actuals end and the projection begins; drawn dashed from there. */
  forecastFrom?: string | number;
  valueFormat?: ValueFormat;
  xAxis?: AxisOptions;
  yAxis?: LinearAxisOptions & { includeZero?: boolean };
  referenceLines?: ReferenceLine[];
  legend?: { show?: boolean };
  height?: number;
  emptyMessage?: string;
}

export interface ResolvedLineSeries {
  name: string;
  values: (number | null)[];
  color: SeriesColor;
  band?: { lower: (number | null)[]; upper: (number | null)[] };
}

export interface ResolvedLineChartSpec {
  title?: string;
  subtitle?: string;
  xType: XType;
  /** Numeric x positions: ms for time, the value for number, index for category. */
  xs: number[];
  /** Display labels for x. */
  xLabels: string[];
  series: ResolvedLineSeries[];
  curve: Curve;
  area: boolean;
  markers: Markers;
  valueLabels: LineValueLabels;
  endLabels: boolean | "auto";
  highlight: string[];
  /** Index into xs where the forecast starts, or -1. */
  forecastIndex: number;
  valueFormat: ValueFormat;
  xAxis: { label?: string; show: boolean };
  yAxis: ResolvedLinearAxis & { includeZero: boolean };
  referenceLines: ReferenceLine[];
  legend: { show: boolean };
  height: number;
  emptyMessage: string;
}

export function normalizeLineChartSpec(input: unknown): Normalized<ResolvedLineChartSpec> {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");

  // Accept `x` or `categories` / `labels` for the x values.
  const xRaw = toArray(raw.x ?? raw.categories ?? raw.labels);
  let xType: XType = pickEnum<XType>(raw.xType, ["time", "number", "category"], "category", "xType", warnings);
  if (raw.xType === undefined && xRaw.length) {
    if (xRaw.every((v) => typeof v === "number")) xType = "number";
    else if (xRaw.every(looksLikeDate)) xType = "time";
  }

  // Resolve x positions, dropping points whose x can't be parsed.
  let keep: number[] = [];
  let xs: number[] = [];
  let xLabels: string[] = [];
  xRaw.forEach((v, i) => {
    if (xType === "time") {
      const t = toDate(v, `x[${i}]`, warnings);
      if (t === null) return;
      keep.push(i);
      xs.push(t);
      xLabels.push(String(v));
    } else if (xType === "number") {
      const n = toNumber(v, `x[${i}]`, warnings);
      if (n === null) return;
      keep.push(i);
      xs.push(n);
      xLabels.push(String(v));
    } else {
      keep.push(i);
      xs.push(xs.length);
      xLabels.push(String(v ?? ""));
    }
  });
  if (xType === "category") xLabels = uniqueNames(xLabels, warnings, "x label");

  // Time and number x must be ascending; sort once and carry series along.
  if (xType !== "category") {
    const order = xs.map((_, i) => i).sort((a, b) => xs[a] - xs[b]);
    if (order.some((o, i) => o !== i)) {
      warnings.push("x values were not in ascending order; sorted.");
      keep = order.map((o) => keep[o]);
      xs = order.map((o) => xs[o]);
      xLabels = order.map((o) => xLabels[o]);
    }
  }

  const pick = (arr: unknown, path: string) => {
    const a = toArray(arr);
    if (a.length !== xRaw.length) warnings.push(`${path} has ${a.length} values for ${xRaw.length} x values.`);
    return keep.map((k) => toNumber(a[k], `${path}[${k}]`, warnings));
  };

  let series = toArray(raw.series).flatMap((s, i) => {
    if (!isObject(s)) {
      warnings.push(`series[${i}] is not an object; dropped.`);
      return [];
    }
    const band = isObject(s.band) ? { lower: pick(s.band.lower, `series[${i}].band.lower`), upper: pick(s.band.upper, `series[${i}].band.upper`) } : undefined;
    return [
      {
        name: optionalString(s.name) ?? `Series ${i + 1}`,
        values: pick(s.values ?? s.data, `series[${i}].values`),
        color: pickColor(s.color, `series[${i}].color`, warnings),
        band,
      },
    ];
  });
  // Single-series shorthand: { x: [...], values: [...] }
  if (!series.length && Array.isArray(raw.values)) {
    series = [{ name: optionalString(raw.seriesName) ?? "Value", values: pick(raw.values, "values"), color: undefined, band: undefined }];
  }

  const names = uniqueNames(series.map((s) => s.name), warnings, "series name");
  const colors = assignColors(series.map((s) => s.color));
  if (series.length > MAX_COLORED_SERIES + 1) {
    warnings.push(`${series.length} lines is too many to tell apart; series after the 4th are drawn grey. Consider highlight or fewer series.`);
  }
  const resolved: ResolvedLineSeries[] = series.map((s, i) => ({ ...s, name: names[i], color: colors[i] }));

  // Forecast start: match by label, then by parsed value.
  let forecastIndex = -1;
  if (raw.forecastFrom !== undefined && raw.forecastFrom !== null) {
    const f = raw.forecastFrom;
    forecastIndex = xLabels.findIndex((l) => l === String(f));
    if (forecastIndex < 0 && xType === "time") {
      const t = toDate(f, "forecastFrom", warnings);
      if (t !== null) forecastIndex = xs.findIndex((x) => x >= t);
    }
    if (forecastIndex < 0 && xType === "number") {
      const n = optionalNumber(f);
      if (n !== undefined) forecastIndex = xs.findIndex((x) => x >= n);
    }
    if (forecastIndex < 0) warnings.push(`forecastFrom ${JSON.stringify(f)} does not match any x value; ignored.`);
  }

  const seriesNames = new Set(names);
  const yAxisRaw = isObject(raw.yAxis) ? raw.yAxis : {};
  const xAxisRaw = isObject(raw.xAxis) ? raw.xAxis : {};
  const legendRaw = isObject(raw.legend) ? raw.legend : {};

  return {
    warnings,
    spec: {
      title: optionalString(raw.title),
      subtitle: optionalString(raw.subtitle),
      xType,
      xs,
      xLabels,
      series: resolved,
      curve: pickEnum<Curve>(raw.curve, ["linear", "monotone", "step"], "monotone", "curve", warnings),
      area: pickBool(raw.area, false),
      markers: pickEnum<Markers>(raw.markers, ["auto", "none", "last", "all"], "auto", "markers", warnings),
      valueLabels: pickEnum<LineValueLabels>(raw.valueLabels, ["auto", "none", "last", "max", "min-max"], "auto", "valueLabels", warnings),
      endLabels: typeof raw.endLabels === "boolean" ? raw.endLabels : "auto",
      highlight: toArray(raw.highlight)
        .map(String)
        .filter((h) => {
          if (!seriesNames.has(h)) warnings.push(`highlight "${h}" is not a series name; ignored.`);
          return seriesNames.has(h);
        }),
      forecastIndex,
      valueFormat: normalizeFormat(raw.valueFormat),
      xAxis: { label: optionalString(xAxisRaw.label), show: xAxisRaw.show !== false },
      yAxis: { ...normalizeLinearAxis(raw.yAxis), includeZero: pickBool(yAxisRaw.includeZero, true) },
      referenceLines: normalizeReferenceLines(raw.referenceLines, warnings),
      legend: { show: typeof legendRaw.show === "boolean" ? legendRaw.show : resolved.length > 1 },
      height: clamp(optionalNumber(raw.height) ?? 300, 160, 800),
      emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
    },
  };
}
