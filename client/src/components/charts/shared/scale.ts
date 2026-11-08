import type { ValueFormat } from "./types";


/**
 * Round, human-friendly ticks covering [min, max].
 * includeZero (default true) — bars and histograms must start at zero; lines and
 * scatter may not.
 */
export function niceTicks(min: number, max: number, count: number, includeZero = true): number[] {
  let lo = includeZero ? Math.min(0, min) : min;
  let hi = includeZero ? Math.max(0, max) : max;
  if (lo === hi) {
    if (lo === 0) hi = 1;
    else {
      const pad = Math.abs(lo) * 0.1;
      lo -= pad;
      hi += pad;
    }
  }
  const step = niceStep((hi - lo) / Math.max(1, count - 1));
  lo = Math.floor(lo / step + 1e-9) * step;
  hi = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

/** Snap a raw step to 1, 2, 2.5 or 5 × 10ⁿ. */
export function niceStep(raw: number): number {
  if (!(raw > 0)) return 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
}

/** Linear map from a domain to a pixel range. */
export function linear(d0: number, d1: number, r0: number, r1: number) {
  const span = d1 - d0 || 1;
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
}

export interface Formatter {
  (value: number): string;
}

/**
 * Build a formatter. `scaleMax` decides "auto" compact notation so every label on
 * one axis shares a style (0 / 10K / 20K, never 0 / 10,000 / 20K).
 */
export function makeFormatter(fmt: ValueFormat, scaleMax: number, forcePercent = false): Formatter {
  if (forcePercent) {
    const nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
    return (v) => `${nf.format(v)}%`;
  }
  const compact = fmt.compact === true || (fmt.compact !== false && Math.abs(scaleMax) >= 10_000);
  const isCurrency = fmt.style === "currency";

  const build = (min: number, max: number) => {
    const opts: Intl.NumberFormatOptions = {
      notation: compact ? "compact" : "standard",
      minimumFractionDigits: min,
      maximumFractionDigits: max,
      ...(isCurrency ? { style: "currency", currency: fmt.currency ?? "USD" } : {}),
    };
    try {
      return new Intl.NumberFormat(undefined, opts);
    } catch {
      return new Intl.NumberFormat(undefined, { maximumFractionDigits: max });
    }
  };

  // Fixed decimals when asked; otherwise whole values print bare and fractions get
  // up to 2 places (exactly 2 for currency, so $45.50 never reads as $45.5).
  const whole = build(fmt.decimals ?? 0, fmt.decimals ?? (compact ? 1 : 0));
  const fractional = build(fmt.decimals ?? (isCurrency && !compact ? 2 : 0), fmt.decimals ?? (compact ? 1 : 2));

  const suffix = (fmt.style === "percent" ? "%" : "") + (fmt.suffix ?? "");
  return (v) => {
    const nf = compact || Number.isInteger(v) ? whole : fractional;
    return `${fmt.prefix ?? ""}${nf.format(v)}${suffix}`;
  };
}

// ---------- text measurement (labels must fit before they are placed) ----------

let ctx: CanvasRenderingContext2D | null | undefined;
const FONT_FAMILY = '"Space Grotesk", ui-sans-serif, system-ui, sans-serif';

export function measureText(text: string, size = 12, weight = 400): number {
  if (ctx === undefined) ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
  if (!ctx) return text.length * size * 0.58;
  ctx.font = `${weight} ${size}px ${FONT_FAMILY}`;
  return ctx.measureText(text).width;
}

/** Trim with an ellipsis until the text fits `maxWidth`. */
export function truncateToWidth(text: string, maxWidth: number, size = 12): string {
  if (measureText(text, size) <= maxWidth) return text;
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (measureText(text.slice(0, mid) + "…", size) <= maxWidth) lo = mid;
    else hi = mid - 1;
  }
  return lo > 0 ? text.slice(0, lo) + "…" : "";
}
