import { assignColors, clamp, isObject, normalizeFormat, optionalNumber, optionalString, pickBool, pickColor, pickEnum, toArray, toNumber, uniqueNames } from "../shared/coerce";
import { MAX_COLORED_SERIES } from "../shared/palette";
import type { Normalized, SeriesColor, ValueFormat } from "../shared/types";

/**
 * Pie / donut spec — one whole split into a few parts.
 * At most 4 coloured slices; the rest fold into a grey "Other".
 * Keep in sync with `pie-chart.schema.json`.
 */

export interface PieSlice {
  label: string;
  value: number;
  color?: SeriesColor;
}

export interface PieChartSpec {
  title?: string;
  subtitle?: string;
  data: PieSlice[];
  /** Ring instead of a full pie. Default true — the hole holds the total. */
  donut?: boolean;
  /** Text in the donut hole. Default: the total, labelled "Total". */
  center?: { value?: string; label?: string };
  /** Largest first (default) or keep the given order. */
  sort?: "desc" | "none";
  valueFormat?: ValueFormat;
  /** Slices with a smaller share than this (0–100) fold into "Other". Default 0. */
  minSharePercent?: number;
  emptyMessage?: string;
}

export interface ResolvedSlice {
  label: string;
  value: number;
  share: number; // 0–1
  color: SeriesColor;
  /** Labels folded into this slice (only for "Other"). */
  folded?: string[];
}

export interface ResolvedPieChartSpec {
  title?: string;
  subtitle?: string;
  slices: ResolvedSlice[];
  total: number;
  donut: boolean;
  center?: { value?: string; label?: string };
  valueFormat: ValueFormat;
  emptyMessage: string;
}

export function normalizePieChartSpec(input: unknown): Normalized<ResolvedPieChartSpec> {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");

  // Accept { data: [{label, value}] } or { categories: [...], values: [...] }.
  let items: { label: string; value: number | null; color?: SeriesColor }[] = [];
  if (Array.isArray(raw.data)) {
    items = raw.data.flatMap((d, i) =>
      isObject(d)
        ? [{ label: String(d.label ?? d.name ?? d.category ?? `Slice ${i + 1}`), value: toNumber(d.value, `data[${i}].value`, warnings), color: pickColor(d.color, `data[${i}].color`, warnings) }]
        : [],
    );
  } else if (Array.isArray(raw.categories)) {
    const values = toArray(raw.values);
    items = raw.categories.map((c, i) => ({ label: String(c), value: toNumber(values[i], `values[${i}]`, warnings) }));
  } else if (isObject(input)) {
    warnings.push("Spec has no `data`; rendering an empty chart.");
  }

  const kept = items.filter((d) => {
    if (d.value === null || d.value === 0) return false;
    if (d.value < 0) {
      warnings.push(`"${d.label}" is negative (${d.value}); a pie can only show positive parts, so it was dropped.`);
      return false;
    }
    return true;
  }) as { label: string; value: number; color?: SeriesColor }[];

  const labels = uniqueNames(kept.map((d) => d.label), warnings, "label");
  let slices = kept.map((d, i) => ({ ...d, label: labels[i] }));
  const sort = pickEnum(raw.sort, ["desc", "none"], "desc", "sort", warnings);
  if (sort === "desc") slices.sort((a, b) => b.value - a.value);

  const total = slices.reduce((a, d) => a + d.value, 0);
  const minShare = clamp(optionalNumber(raw.minSharePercent) ?? 0, 0, 50) / 100;

  // Fold: anything past the 4th slice, and anything under minShare.
  let folded: typeof slices = [];
  if (minShare > 0) {
    folded = slices.filter((s) => s.value / total < minShare);
    slices = slices.filter((s) => s.value / total >= minShare);
  }
  if (slices.length > MAX_COLORED_SERIES) {
    folded = [...slices.slice(MAX_COLORED_SERIES), ...folded];
    slices = slices.slice(0, MAX_COLORED_SERIES);
  }
  const colors = assignColors(slices.map((s) => s.color));
  const resolved: ResolvedSlice[] = slices.map((s, i) => ({ label: s.label, value: s.value, share: total ? s.value / total : 0, color: colors[i] }));
  if (folded.length === 1 && resolved.length < MAX_COLORED_SERIES + 1) {
    // A single leftover keeps its own name, in grey.
    const f = folded[0];
    resolved.push({ label: f.label, value: f.value, share: f.value / total, color: "neutral" });
  } else if (folded.length) {
    const v = folded.reduce((a, s) => a + s.value, 0);
    warnings.push(`${folded.length} small slices folded into "Other": ${folded.map((f) => f.label).join(", ")}.`);
    resolved.push({ label: "Other", value: v, share: v / total, color: "neutral", folded: folded.map((f) => f.label) });
  }
  if (resolved.length === 2) warnings.push("A 2-slice pie reads better as a single number or a progress meter.");

  const center = isObject(raw.center) ? { value: optionalString(raw.center.value), label: optionalString(raw.center.label) } : undefined;

  return {
    warnings,
    spec: {
      title: optionalString(raw.title),
      subtitle: optionalString(raw.subtitle),
      slices: resolved,
      total,
      donut: pickBool(raw.donut, true),
      center,
      valueFormat: normalizeFormat(raw.valueFormat),
      emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
    },
  };
}
