import {
  assignColors,
  clamp,
  isObject,
  normalizeFormat,
  normalizeReferenceLines,
  optionalNumber,
  optionalString,
  pickColor,
  pickEnum,
  sumNullable,
  toArray,
  toNumber,
  uniqueNames,
} from "../shared/coerce";
import { MAX_COLORED_SERIES } from "../shared/palette";
import type {
  BarLayout,
  NormalizeResult,
  Orientation,
  ResolvedBarChartSpec,
  SeriesColor,
  SortOrder,
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
          color: pickColor(s.color, `series[${i}].color`, warnings),
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
  categories = uniqueNames(categories, warnings, "category");

  // Colour: explicit pins first, then fill remaining series from the palette in order.
  const colors = assignColors(series.map((s) => s.color));
  let resolved = series.map((s, i) => ({ ...s, color: colors[i] }));

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
  const sort = pickEnum<SortOrder>(({ ascending: "asc", descending: "desc", none: "none" } as Record<string, string>)[String(raw.sort)] ?? raw.sort, ["none", "asc", "desc"], "none", "sort", warnings);

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
    referenceLines: normalizeReferenceLines(raw.referenceLines, warnings),
    sort,
    height: clamp(optionalNumber(raw.height) ?? 320, 160, 800),
    emptyMessage: optionalString(raw.emptyMessage) ?? "No data to show yet.",
  };

  return { spec, warnings };
}
