/**
 * Time axis helpers. Everything is UTC so "2026-03-01" never drifts to Feb 28
 * in a negative-offset timezone.
 */

export const DAY = 86_400_000;

type Unit = "day" | "week" | "month" | "year";
interface Interval {
  unit: Unit;
  step: number;
  approx: number; // ms, used only to choose the interval
}

const INTERVALS: Interval[] = [
  { unit: "day", step: 1, approx: DAY },
  { unit: "day", step: 2, approx: 2 * DAY },
  { unit: "week", step: 1, approx: 7 * DAY },
  { unit: "week", step: 2, approx: 14 * DAY },
  { unit: "month", step: 1, approx: 30.4 * DAY },
  { unit: "month", step: 3, approx: 91 * DAY },
  { unit: "month", step: 6, approx: 182 * DAY },
  { unit: "year", step: 1, approx: 365 * DAY },
  { unit: "year", step: 2, approx: 730 * DAY },
  { unit: "year", step: 5, approx: 1826 * DAY },
  { unit: "year", step: 10, approx: 3652 * DAY },
];

export interface TimeTick {
  value: number;
  text: string;
}

/** Calendar-aligned ticks (1st of month, Mondays, Jan 1…) inside [t0, t1]. */
export function timeTicks(t0: number, t1: number, maxCount: number): TimeTick[] {
  const span = Math.max(t1 - t0, DAY);
  const interval = INTERVALS.find((i) => span / i.approx <= maxCount) ?? INTERVALS[INTERVALS.length - 1];
  const values: number[] = [];
  let t = floorTo(t0, interval);
  if (t < t0) t = advance(t, interval);
  for (let guard = 0; t <= t1 && guard < 500; guard++) {
    values.push(t);
    t = advance(t, interval);
  }
  const multiYear = new Date(t0).getUTCFullYear() !== new Date(t1).getUTCFullYear();
  return values.map((v, i) => ({ value: v, text: formatTick(v, interval.unit, i === 0, multiYear) }));
}

function floorTo(t: number, { unit, step }: Interval): number {
  const d = new Date(t);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  if (unit === "year") return Date.UTC(Math.floor(y / step) * step, 0, 1);
  if (unit === "month") return Date.UTC(y, Math.floor(m / step) * step, 1);
  const day = Date.UTC(y, m, d.getUTCDate());
  if (unit === "week") {
    const dow = (new Date(day).getUTCDay() + 6) % 7; // Monday = 0
    return day - dow * DAY;
  }
  return day;
}

function advance(t: number, { unit, step }: Interval): number {
  const d = new Date(t);
  if (unit === "year") return Date.UTC(d.getUTCFullYear() + step, 0, 1);
  if (unit === "month") return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + step, 1);
  return t + (unit === "week" ? 7 * step : step) * DAY;
}

const fmt = (opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(undefined, { timeZone: "UTC", ...opts });
const fYear = fmt({ year: "numeric" });
const fMonth = fmt({ month: "short" });
const fMonthYear = fmt({ month: "short", year: "numeric" });
const fDay = fmt({ month: "short", day: "numeric" });
const fFull = fmt({ month: "short", day: "numeric", year: "numeric" });

function formatTick(t: number, unit: Unit, first: boolean, multiYear: boolean): string {
  const d = new Date(t);
  if (unit === "year") return fYear.format(d);
  if (unit === "month") return first || d.getUTCMonth() === 0 || (multiYear && first) ? fMonthYear.format(d) : fMonth.format(d);
  return fDay.format(d);
}

/** "Mar 4, 2026" — for tooltips and tables. */
export function formatDate(t: number): string {
  return fFull.format(new Date(t));
}

/** "Mar 4 – Apr 12, 2026" */
export function formatDateRange(a: number, b: number): string {
  return `${formatDate(a)} – ${formatDate(b)}`;
}

export function daysBetween(a: number, b: number): number {
  return Math.round((b - a) / DAY);
}
