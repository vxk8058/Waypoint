import { CATEGORICAL_ORDER, MAX_COLORED_SERIES, SERIES_COLORS } from "./palette";
import type {
  BarLayout,
  NormalizeResult,
  Orientation,
  ResolvedBarChartSpec,
  SeriesColor,
  SortOrder,
  ValueFormat,
  ValueLabels,
} from "./types";

/**
 * Turns whatever the model sent into a spec that is safe to render.
 * Never throws: bad fields fall back to defaults and are reported in `warnings`.
 *
 * Accepted input shapes:
 *   { categories: [...], series: [{ name, values: [...] }] }       — canonical
 *   { data: [{ label, value }], seriesName? }                       — single-series shorthand
 *   series[].data is accepted as an alias for series[].values
 *   numbers may arrive as strings ("1,200", "$45.50", "12%")
 */
export function normalizeBarChartSpec(input: unknown): NormalizeResult {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");

  let categories: string[] = [];
  let series: { name: string; values: (number | null)[]; color?: SeriesColor }[] = [];

  if (Array.isArray(raw.categories) || Array.isArray(raw.series)) {
    categories = toArray(raw.categories).map((c) => String(c ?? ""));
    series = toArray(raw.series).flatMap((s, i) => {
      if (!isObject(s)) {
        warnings.push(`series[${i}] is not an object; dropped.`);
        return [];
      }
      const valuesRaw = Array.isArray(s.values) ? s.values : Array.isArray(s.data) ? s.data : [];
      const values = valuesRaw.map((v, j) => toNumber(v, `series[${i}].values[${j}]`, warnings));
      if (values.length !== categories.length) {
        warnings.push(
          `series[${i}] has ${values.length} values for ${categories.length} categories; ` +
            (values.length > categories.length ? "extra values dropped." : "missing values treated as no data."),
        );
      }
      values.length = categories.length;
      return [
        {
          name: typeof s.name === "string" && s.name.trim() ? s.name : `Series ${i + 1}`,
          values: Array.from(values, (v) => v ?? null),
          color: pickEnum(s.color, Object.keys(SERIES_COLORS) as SeriesColor[], undefined, `series[${i}].color`, warnings),
        },
      ];
    });
  } else if (Array.isArray(raw.data)) {
    const rows = raw.data.filter(isObject);
    categories = rows.map((r) => String(r.label ?? r.category ?? r.name ?? ""));
    series = [
      {
        name: typeof raw.seriesName === "string" ? raw.seriesName : "Value",
        values: rows.map((r, j) => toNumber(r.value, `data[${j}].value`, warnings)),
      },
    ];
  } else if (isObject(input)) {
    warnings.push("Spec has no `categories`/`series` or `data`; rendering an empty chart.");
  }

  // Duplicate category names would collide as keys and confuse the tooltip.
  const seen = new Map<string, number>();
  categories = categories.map((c) => {
    const n = seen.get(c) ?? 0;
    seen.set(c, n + 1);
    if (n > 0) warnings.push(`Duplicate category "${c}" renamed to "${c} (${n + 1})".`);
    return n > 0 ? `${c} (${n + 1})` : c;
  });

  // Colour: explicit pins first, then fill remaining series from the palette in order.
  const pinned = new Set(series.map((s) => s.color).filter(Boolean));
  const free = CATEGORICAL_ORDER.filter((c) => !pinned.has(c));
  let resolved = series.map((s) => ({ ...s, color: s.color ?? free.shift() ?? ("neutral" as SeriesColor) }));

  // More than four hues stop being distinguishable — fold the tail into "Other".
  if (resolved.length > MAX_COLORED_SERIES + 1) {
    const kept = resolved.slice(0, MAX_COLORED_SERIES);
    const rest = resolved.slice(MAX_COLORED_SERIES);
    warnings.push(
      `${resolved.length} series is too many to tell apart; ${rest.map((s) => s.name).join(", ")} folded into "Other".`,
    );
    resolved = [
      ...kept,
      {
        name: "Other",
        color: "neutral",
        values: categories.map((_, j) => sumNullable(rest.map((s) => s.values[j]))),
      },
    ];
  }

  const layout = pickEnum<BarLayout>(raw.layout, ["grouped", "stacked", "percent"], "grouped", "layout", warnings);
  const orientation = pickEnum<Orientation>(raw.orientation, ["vertical", "horizontal"], "vertical", "orientation", warnings);
  const valueLabels = pickEnum<ValueLabels>(
    raw.valueLabels,
    ["auto", "none", "all", "max", "min-max", "last", "totals"],
    "auto",
    "valueLabels",
    warnings,
  );
  const sort = pickEnum<SortOrder>(raw.sort, ["none", "asc", "desc"], "none", "sort", warnings);

  if (layout === "percent" && resolved.some((s) => s.values.some((v) => v !== null && v < 0))) {
    warnings.push("Percent layout uses absolute values; negative values are shown as their share of the total.");
  }

  const valueAxisRaw = isObject(raw.valueAxis) ? raw.valueAxis : {};
  let min = optionalNumber(valueAxisRaw.min);
  let max = optionalNumber(valueAxisRaw.max);
  if (min !== undefined && min > 0) {
    warnings.push("valueAxis.min must be ≤ 0 so bars start at zero; clamped to 0.");
    min = 0;
  }
  if (max !== undefined && max < 0) {
    warnings.push("valueAxis.max must be ≥ 0 so bars start at zero; clamped to 0.");
    max = 0;
  }

  const categoryAxisRaw = isObject(raw.categoryAxis) ? raw.categoryAxis : {};
  const legendRaw = isObject(raw.legend) ? raw.legend : {};
  const categorySet = new Set(categories);

  const spec: ResolvedBarChartSpec = {
    title: optionalString(raw.title),
    subtitle: optionalString(raw.subtitle),
    categories,
    series: resolved,
    orientation,
    layout,
    valueFormat: normalizeFormat(raw.valueFormat),
    categoryAxis: {
      label: optionalString(categoryAxisRaw.label),
      show: categoryAxisRaw.show !== false,
    },
    valueAxis: {
      label: optionalString(valueAxisRaw.label),
      show: valueAxisRaw.show !== false,
      gridlines: valueAxisRaw.gridlines !== false,
      tickCount: clamp(optionalNumber(valueAxisRaw.tickCount) ?? 5, 2, 10),
      min,
      max,
    },
    valueLabels,
    legend: { show: typeof legendRaw.show === "boolean" ? legendRaw.show : resolved.length > 1 },
    highlight: toArray(raw.highlight)
      .map(String)
      .filter((h) => {
        if (!categorySet.has(h)) warnings.push(`highlight "${h}" is not a category; ignored.`);
        return categorySet.has(h);
      }),
    referenceLines: toArray(raw.referenceLines).flatMap((r, i) => {
      const value = isObject(r) ? toNumber(r.value, `referenceLines[${i}].value`, warnings) : null;
      if (value === null) return [];
      return [{ value, label: isObject(r) ? optionalString(r.label) : undefined }];
    }),
    sort,
    height: clamp(optionalNumber(raw.height) ?? 320, 160, 800),
    emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
  };

  return { spec, warnings };
}

function normalizeFormat(input: unknown): ValueFormat {
  if (!isObject(input)) return {};
  const style = input.style === "currency" || input.style === "percent" ? input.style : "number";
  const decimals = optionalNumber(input.decimals);
  return {
    style,
    currency: typeof input.currency === "string" && /^[A-Za-z]{3}$/.test(input.currency) ? input.currency.toUpperCase() : "USD",
    decimals: decimals === undefined ? undefined : clamp(Math.round(decimals), 0, 6),
    compact: typeof input.compact === "boolean" ? input.compact : "auto",
    prefix: optionalString(input.prefix),
    suffix: optionalString(input.suffix),
  };
}

// ---------- small coercion helpers ----------

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function toArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function optionalString(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() ? v : undefined;
}

function optionalNumber(v: unknown): number | undefined {
  const n = typeof v === "string" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : undefined;
}

function toNumber(v: unknown, path: string, warnings: string[]): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string") {
    const cleaned = v.replace(/[\s,$€£¥%]/g, "");
    const n = Number(cleaned);
    if (cleaned && Number.isFinite(n)) return n;
  }
  warnings.push(`${path} is not a number (${JSON.stringify(v)}); treated as no data.`);
  return null;
}

function pickEnum<T extends string>(
  v: unknown,
  allowed: readonly T[],
  fallback: T,
  path: string,
  warnings: string[],
): T;
function pickEnum<T extends string>(
  v: unknown,
  allowed: readonly T[],
  fallback: undefined,
  path: string,
  warnings: string[],
): T | undefined;
function pickEnum<T extends string>(
  v: unknown,
  allowed: readonly T[],
  fallback: T | undefined,
  path: string,
  warnings: string[],
): T | undefined {
  if (v === undefined || v === null) return fallback;
  if (typeof v === "string" && (allowed as readonly string[]).includes(v)) return v as T;
  warnings.push(`${path} "${String(v)}" is not one of ${allowed.join(", ")}; using ${fallback ?? "default"}.`);
  return fallback;
}

function sumNullable(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null);
  return present.length ? present.reduce((a, b) => a + b, 0) : null;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}
