import { isObject, normalizeFormat, optionalNumber, optionalString, pickEnum, toArray, toNumber } from "../charts/shared/coerce";
import type { Normalized, ValueFormat } from "../charts/shared/types";

/* ------------------------------------------------------------------ specs */

export interface HeadingSpec {
  text: string;
  /** 1 = section title, 2 = sub-section, 3 = small heading. */
  level: 1 | 2 | 3;
}

export interface ParagraphSpec {
  /** Inline Markdown allowed. Blank lines split paragraphs. */
  text: string;
  tone: "default" | "muted";
  size: "default" | "lead" | "small";
}

export interface ListSpec {
  items: string[];
  ordered: boolean;
}

export type CalloutTone = "info" | "success" | "warning" | "danger";
export interface CalloutSpec {
  tone: CalloutTone;
  title?: string;
  text: string;
}

export interface StatItem {
  label: string;
  /** Pre-formatted string, or a number formatted with `format`. */
  value: string;
  /** Change vs. the comparison period, already formatted ("+12%"). */
  change?: string;
  /** Direction of the change, drives the arrow. */
  direction?: "up" | "down" | "flat";
  /** Whether the change is good, bad, or neither. Drives colour. */
  sentiment: "positive" | "negative" | "neutral";
  caption?: string;
}
export interface StatsSpec {
  items: StatItem[];
}

export type DividerSpec = Record<string, never>;

/* ------------------------------------------------------------ normalizers */

function textOf(input: Record<string, unknown>, warnings: string[]): string {
  const t = input.text ?? input.content ?? input.body ?? input.markdown ?? input.value;
  if (typeof t === "string") return t.trim();
  if (typeof t === "number") return String(t);
  if (Array.isArray(t)) return t.filter((x) => typeof x === "string").join("\n\n").trim();
  warnings.push("text: missing or not a string");
  return "";
}

export function normalizeHeadingSpec(input: unknown): Normalized<HeadingSpec> {
  const warnings: string[] = [];
  const o = typeof input === "string" ? { text: input } : isObject(input) ? input : {};
  const raw = optionalNumber(typeof o.level === "string" ? o.level.replace(/^h/i, "") : o.level) ?? 1;
  const level = Math.min(3, Math.max(1, Math.round(raw))) as 1 | 2 | 3;
  if (raw !== level) warnings.push(`level: ${String(o.level)} → ${level}`);
  return { spec: { text: textOf(o, warnings), level }, warnings };
}

export function normalizeParagraphSpec(input: unknown): Normalized<ParagraphSpec> {
  const warnings: string[] = [];
  const o = typeof input === "string" ? { text: input } : isObject(input) ? input : {};
  return {
    spec: {
      text: textOf(o, warnings),
      tone: pickEnum(o.tone, ["default", "muted"] as const, "default", "tone", warnings),
      size: pickEnum(o.size, ["default", "lead", "small"] as const, "default", "size", warnings),
    },
    warnings,
  };
}

export function normalizeListSpec(input: unknown): Normalized<ListSpec> {
  const warnings: string[] = [];
  const o = Array.isArray(input) ? { items: input } : isObject(input) ? input : {};
  const items = toArray(o.items ?? o.bullets ?? o.points).flatMap((it, i) => {
    if (typeof it === "string" && it.trim()) return [it.trim()];
    if (typeof it === "number") return [String(it)];
    if (isObject(it) && typeof (it.text ?? it.label) === "string") return [String(it.text ?? it.label)];
    warnings.push(`items[${i}]: not text, dropped`);
    return [];
  });
  if (!items.length) warnings.push("items: empty");
  return { spec: { items, ordered: o.ordered === true || o.style === "numbered" }, warnings };
}

export function normalizeCalloutSpec(input: unknown): Normalized<CalloutSpec> {
  const warnings: string[] = [];
  const o = typeof input === "string" ? { text: input } : isObject(input) ? input : {};
  const toneAlias: Record<string, CalloutTone> = { error: "danger", critical: "danger", warn: "warning", tip: "success", good: "success", note: "info" };
  const rawTone = typeof o.tone === "string" ? (toneAlias[o.tone] ?? o.tone) : o.tone;
  return {
    spec: {
      tone: pickEnum(rawTone, ["info", "success", "warning", "danger"] as const, "info", "tone", warnings),
      title: optionalString(o.title),
      text: textOf(o, warnings),
    },
    warnings,
  };
}

export function normalizeStatsSpec(input: unknown): Normalized<StatsSpec> {
  const warnings: string[] = [];
  const o = Array.isArray(input) ? { items: input } : isObject(input) ? input : {};
  // A single stat may be sent flat: { label, value }.
  const list = o.items ?? o.stats ?? (o.label !== undefined ? [o] : []);
  const items = toArray(list).flatMap((it, i): StatItem[] => {
    if (!isObject(it)) {
      warnings.push(`items[${i}]: not an object, dropped`);
      return [];
    }
    const label = optionalString(it.label ?? it.name ?? it.title);
    if (!label) {
      warnings.push(`items[${i}]: missing label, dropped`);
      return [];
    }
    const fmt: ValueFormat = normalizeFormat(it.format);
    let value: string;
    if (typeof it.value === "string" && !/^[\s$€£,.\d%+-]+$/.test(it.value)) value = it.value;
    else {
      const n = toNumber(it.value, `items[${i}].value`, warnings);
      value = n === null ? "—" : formatValue(n, fmt);
    }

    let change: string | undefined;
    let direction: StatItem["direction"];
    if (typeof it.change === "string" && it.change.trim()) {
      change = it.change.trim();
      direction = change.startsWith("-") || change.startsWith("−") ? "down" : /^0(\.0+)?%?$/.test(change.replace(/^\+/, "")) ? "flat" : "up";
    } else if (typeof it.change === "number" && Number.isFinite(it.change)) {
      const style = it.changeFormat === "number" ? "number" : it.changeFormat === "currency" ? "currency" : "percent";
      const abs = Math.abs(it.change);
      const body = style === "percent" ? `${trim(abs)}%` : formatValue(abs, { ...fmt, style: style === "currency" ? "currency" : fmt.style });
      direction = it.change > 0 ? "up" : it.change < 0 ? "down" : "flat";
      change = `${it.change > 0 ? "+" : it.change < 0 ? "−" : ""}${body}`;
    }
    if (it.direction === "up" || it.direction === "down" || it.direction === "flat") direction = it.direction;

    // Sentiment: explicit, else from goodDirection ("up" by default).
    let sentiment: StatItem["sentiment"] = "neutral";
    if (it.sentiment === "positive" || it.sentiment === "negative" || it.sentiment === "neutral") sentiment = it.sentiment;
    else if (direction && direction !== "flat") {
      const good = it.goodDirection === "down" ? "down" : it.goodDirection === "none" ? null : "up";
      sentiment = good === null ? "neutral" : direction === good ? "positive" : "negative";
    }

    return [{ label, value, change, direction: change ? direction : undefined, sentiment, caption: optionalString(it.caption ?? it.changeLabel) }];
  });
  if (!items.length) warnings.push("items: empty");
  if (items.length > 4) warnings.push("items: more than 4 stats reads poorly; consider a table or chart");
  return { spec: { items }, warnings };
}

function trim(n: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(n);
}

function formatValue(n: number, fmt: ValueFormat) {
  const compact = fmt.compact === true || (fmt.compact !== false && Math.abs(n) >= 100_000);
  const opts: Intl.NumberFormatOptions = {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: fmt.decimals ?? (compact ? 1 : Number.isInteger(n) ? 0 : 2),
    minimumFractionDigits: fmt.decimals ?? (fmt.style === "currency" && !compact && !Number.isInteger(n) ? 2 : 0),
    ...(fmt.style === "currency" ? { style: "currency", currency: fmt.currency ?? "USD" } : {}),
  };
  let s: string;
  try {
    s = new Intl.NumberFormat(undefined, opts).format(n);
  } catch {
    s = String(n);
  }
  return `${fmt.prefix ?? ""}${s}${fmt.style === "percent" ? "%" : ""}${fmt.suffix ?? ""}`;
}
