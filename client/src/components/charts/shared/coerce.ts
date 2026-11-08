import { CATEGORICAL_ORDER, SERIES_COLORS } from "./palette";
import type { LinearAxisOptions, ReferenceLine, SeriesColor, ValueFormat } from "./types";

/**
 * Small, forgiving coercion helpers shared by every chart normaliser.
 * They never throw; anything they fix is appended to `warnings`.
 */

export function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function toArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

export function optionalString(v: unknown): string | undefined {
  if (typeof v === "number") return String(v);
  return typeof v === "string" && v.trim() ? v : undefined;
}

export function optionalNumber(v: unknown): number | undefined {
  const n = typeof v === "string" && v.trim() !== "" ? Number(v) : v;
  return typeof n === "number" && Number.isFinite(n) ? n : undefined;
}

export function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

/** Accepts numbers and number-ish strings ("1,200", "$45.50", "12%"). */
export function toNumber(v: unknown, path: string, warnings: string[]): number | null {
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

/**
 * Dates as UTC milliseconds. Accepts ISO strings ("2026-03-01", "2026-03"),
 * epoch milliseconds, or Date objects.
 */
export function toDate(v: unknown, path: string, warnings: string[]): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (v instanceof Date) return Number.isNaN(v.getTime()) ? null : v.getTime();
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const iso = /^\d{4}-\d{2}$/.test(v) ? `${v}-01` : v;
    const t = Date.parse(iso);
    if (!Number.isNaN(t)) return t;
  }
  warnings.push(`${path} is not a date (${JSON.stringify(v)}); ignored.`);
  return null;
}

export function looksLikeDate(v: unknown): boolean {
  return typeof v === "string" && /^\d{4}-\d{2}(-\d{2})?([T ][\d:.]+Z?)?$/.test(v) && !Number.isNaN(Date.parse(v.length === 7 ? `${v}-01` : v));
}

export function pickEnum<T extends string>(v: unknown, allowed: readonly T[], fallback: T, path: string, warnings: string[]): T;
export function pickEnum<T extends string>(v: unknown, allowed: readonly T[], fallback: undefined, path: string, warnings: string[]): T | undefined;
export function pickEnum<T extends string>(
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

export function pickBool(v: unknown, fallback: boolean): boolean {
  return typeof v === "boolean" ? v : fallback;
}

export function sumNullable(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null);
  return present.length ? present.reduce((a, b) => a + b, 0) : null;
}

export function pickColor(v: unknown, path: string, warnings: string[]): SeriesColor | undefined {
  return pickEnum(v, Object.keys(SERIES_COLORS) as SeriesColor[], undefined, path, warnings);
}

/**
 * Resolve colours: explicit pins first, then the palette in fixed order, then
 * neutral. `maxColored` caps how many hues may appear (3 for all-pairs forms
 * like scatter, 4 for adjacent forms).
 */
export function assignColors(pins: (SeriesColor | undefined)[], maxColored = CATEGORICAL_ORDER.length): SeriesColor[] {
  const pinned = new Set(pins.filter(Boolean));
  const free = CATEGORICAL_ORDER.slice(0, maxColored).filter((c) => !pinned.has(c));
  return pins.map((p) => p ?? free.shift() ?? "neutral");
}

/** Make names unique so they can be used as keys ("Rent", "Rent (2)"). */
export function uniqueNames(names: string[], warnings: string[], what = "name"): string[] {
  const seen = new Map<string, number>();
  return names.map((c) => {
    const n = seen.get(c) ?? 0;
    seen.set(c, n + 1);
    if (n > 0) warnings.push(`Duplicate ${what} "${c}" renamed to "${c} (${n + 1})".`);
    return n > 0 ? `${c} (${n + 1})` : c;
  });
}

export function normalizeFormat(input: unknown): ValueFormat {
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

export function normalizeReferenceLines(input: unknown, warnings: string[], path = "referenceLines"): ReferenceLine[] {
  return toArray(input).flatMap((r, i) => {
    const value = isObject(r) ? toNumber(r.value, `${path}[${i}].value`, warnings) : null;
    if (value === null) return [];
    return [{ value, label: isObject(r) ? optionalString(r.label) : undefined }];
  });
}

export type ResolvedLinearAxis = Required<Pick<LinearAxisOptions, "show" | "gridlines" | "tickCount">> & LinearAxisOptions;

export function normalizeLinearAxis(input: unknown, defaults: { gridlines?: boolean } = {}): ResolvedLinearAxis {
  const a = isObject(input) ? input : {};
  return {
    label: optionalString(a.label),
    show: a.show !== false,
    gridlines: pickBool(a.gridlines, defaults.gridlines ?? true),
    tickCount: clamp(optionalNumber(a.tickCount) ?? 5, 2, 10),
    min: optionalNumber(a.min),
    max: optionalNumber(a.max),
  };
}
