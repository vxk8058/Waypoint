import {
  assignColors,
  clamp,
  isObject,
  normalizeFormat,
  normalizeLinearAxis,
  optionalNumber,
  optionalString,
  pickColor,
  pickEnum,
  toArray,
  toNumber,
  uniqueNames,
} from "../shared/coerce";
import type { ResolvedLinearAxis } from "../shared/coerce";
import type { LinearAxisOptions, Normalized, ReferenceLine, SeriesColor, ValueFormat } from "../shared/types";

/**
 * Scatter plot spec — the relationship between two measures.
 * At most 3 coloured groups (every pair must stay distinguishable); more fold into grey "Other".
 * Keep in sync with `scatter-plot.schema.json`.
 */

export const MAX_SCATTER_GROUPS = 3;

export interface ScatterPoint {
  x: number;
  y: number;
  label?: string;
  /** Optional third measure, drawn as dot area (bubble chart). */
  size?: number;
}

export interface ScatterSeries {
  name: string;
  points: ScatterPoint[];
  color?: SeriesColor;
}

export type PointLabels = "auto" | "none" | "highlighted" | "all";

export interface ScatterPlotSpec {
  title?: string;
  subtitle?: string;
  /** Grouped points. Or use `points` for a single group. */
  series?: ScatterSeries[];
  points?: ScatterPoint[];
  xAxis?: LinearAxisOptions & { format?: ValueFormat; includeZero?: boolean };
  yAxis?: LinearAxisOptions & { format?: ValueFormat; includeZero?: boolean };
  /** What `size` means, shown in the tooltip. */
  sizeLabel?: string;
  /** Least-squares trend line: none, one across all points, or one per group. */
  trendline?: "none" | "all" | "per-series";
  /** Point labels to emphasise (others dim). */
  highlight?: string[];
  /** auto: label highlighted points, or all if there are ≤ 12. */
  labels?: PointLabels;
  referenceLines?: { x?: ReferenceLine[]; y?: ReferenceLine[] };
  height?: number;
  emptyMessage?: string;
}

export interface ResolvedPoint extends ScatterPoint {
  series: number;
}

export interface ResolvedScatterSpec {
  title?: string;
  subtitle?: string;
  series: { name: string; color: SeriesColor }[];
  points: ResolvedPoint[];
  xAxis: ResolvedLinearAxis & { format: ValueFormat; includeZero: boolean };
  yAxis: ResolvedLinearAxis & { format: ValueFormat; includeZero: boolean };
  sizeLabel?: string;
  hasSize: boolean;
  trendline: "none" | "all" | "per-series";
  highlight: string[];
  labels: PointLabels;
  referenceLines: { x: ReferenceLine[]; y: ReferenceLine[] };
  height: number;
  emptyMessage: string;
}

export function normalizeScatterSpec(input: unknown): Normalized<ResolvedScatterSpec> {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");

  const readPoints = (arr: unknown, path: string): ScatterPoint[] =>
    toArray(arr).flatMap((p, i) => {
      // Accept {x, y} objects or [x, y] pairs.
      const o: Record<string, unknown> | null = Array.isArray(p) ? { x: p[0], y: p[1] } : isObject(p) ? p : null;
      if (!o) return [];
      const x = toNumber(o.x, `${path}[${i}].x`, warnings);
      const y = toNumber(o.y, `${path}[${i}].y`, warnings);
      if (x === null || y === null) return [];
      const size = o.size === undefined ? undefined : (toNumber(o.size, `${path}[${i}].size`, warnings) ?? undefined);
      return [{ x, y, label: optionalString(o.label), size: size !== undefined && size >= 0 ? size : undefined }];
    });

  let groups: { name: string; points: ScatterPoint[]; color?: SeriesColor }[] = [];
  if (Array.isArray(raw.series)) {
    groups = raw.series.flatMap((s, i) =>
      isObject(s) ? [{ name: optionalString(s.name) ?? `Group ${i + 1}`, points: readPoints(s.points ?? s.data, `series[${i}].points`), color: pickColor(s.color, `series[${i}].color`, warnings) }] : [],
    );
  } else if (Array.isArray(raw.points)) {
    groups = [{ name: optionalString(raw.seriesName) ?? "Points", points: readPoints(raw.points, "points") }];
  } else if (isObject(input)) {
    warnings.push("Spec has no `series` or `points`; rendering an empty chart.");
  }

  const names = uniqueNames(groups.map((g) => g.name), warnings, "series name");
  groups = groups.map((g, i) => ({ ...g, name: names[i] }));
  if (groups.length > MAX_SCATTER_GROUPS + 1) {
    const rest = groups.slice(MAX_SCATTER_GROUPS);
    warnings.push(`Scatter plots stay readable with ≤ 3 coloured groups; ${rest.map((g) => g.name).join(", ")} folded into "Other".`);
    groups = [...groups.slice(0, MAX_SCATTER_GROUPS), { name: "Other", points: rest.flatMap((g) => g.points), color: "neutral" }];
  }
  const colors = assignColors(groups.map((g) => g.color), MAX_SCATTER_GROUPS);

  const points: ResolvedPoint[] = groups.flatMap((g, si) => g.points.map((p) => ({ ...p, series: si })));
  const hasSize = points.some((p) => p.size !== undefined);

  const axis = (v: unknown) => {
    const a = isObject(v) ? v : {};
    return { ...normalizeLinearAxis(v), format: normalizeFormat(a.format), includeZero: a.includeZero === true };
  };
  const refs = isObject(raw.referenceLines) ? raw.referenceLines : {};
  const readRefs = (arr: unknown, path: string) =>
    toArray(arr).flatMap((r, i) => {
      const value = isObject(r) ? toNumber(r.value, `${path}[${i}].value`, warnings) : null;
      return value === null ? [] : [{ value, label: isObject(r) ? optionalString(r.label) : undefined }];
    });

  const labelSet = new Set(points.map((p) => p.label).filter(Boolean));

  return {
    warnings,
    spec: {
      title: optionalString(raw.title),
      subtitle: optionalString(raw.subtitle),
      series: groups.map((g, i) => ({ name: g.name, color: colors[i] })),
      points,
      xAxis: axis(raw.xAxis),
      yAxis: axis(raw.yAxis),
      sizeLabel: optionalString(raw.sizeLabel),
      hasSize,
      trendline: pickEnum(raw.trendline === true ? "all" : raw.trendline === false ? "none" : raw.trendline, ["none", "all", "per-series"], "none", "trendline", warnings),
      highlight: toArray(raw.highlight)
        .map(String)
        .filter((h) => {
          if (!labelSet.has(h)) warnings.push(`highlight "${h}" matches no point label; ignored.`);
          return labelSet.has(h);
        }),
      labels: pickEnum<PointLabels>(raw.labels, ["auto", "none", "highlighted", "all"], "auto", "labels", warnings),
      referenceLines: { x: readRefs(refs.x, "referenceLines.x"), y: readRefs(refs.y, "referenceLines.y") },
      height: clamp(optionalNumber(raw.height) ?? 320, 180, 800),
      emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
    },
  };
}
