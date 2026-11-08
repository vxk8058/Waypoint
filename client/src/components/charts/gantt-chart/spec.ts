import { assignColors, isObject, optionalNumber, optionalString, pickColor, pickEnum, toArray, toDate, uniqueNames } from "../shared/coerce";
import { MAX_COLORED_SERIES } from "../shared/palette";
import { DAY } from "../shared/time";
import type { Normalized, SeriesColor } from "../shared/types";

/**
 * Gantt chart spec — tasks or goal phases on a calendar.
 * Keep in sync with `gantt-chart.schema.json`.
 */

export interface GanttTask {
  /** Used by `dependsOn`. Defaults to the task name. */
  id?: string;
  name: string;
  /** ISO date, e.g. "2026-03-01". */
  start: string;
  /** ISO date. Or give `durationDays`. Omit both for a milestone. */
  end?: string;
  durationDays?: number;
  /** 0–1 or 0–100. */
  progress?: number;
  /** Tasks in the same group share a colour. */
  group?: string;
  /** A single date, drawn as a diamond. */
  milestone?: boolean;
  /** ids (or names) of tasks that must finish first. */
  dependsOn?: string[];
}

export type GanttLabels = "auto" | "none" | "progress" | "duration" | "dates";

export interface GanttChartSpec {
  title?: string;
  subtitle?: string;
  tasks: GanttTask[];
  /** Pin colours per group name. */
  groupColors?: Record<string, SeriesColor>;
  /** Show a "Today" rule. true / false / an ISO date. Default: shown when today is in range. */
  today?: boolean | string;
  /** Extra dated rules, e.g. a deadline. */
  markers?: { date: string; label?: string }[];
  /** Text after each bar. auto: progress when any task has it. */
  labels?: GanttLabels;
  /** Visible date range; defaults to the tasks' span. */
  range?: { start?: string; end?: string };
  emptyMessage?: string;
}

export interface ResolvedTask {
  id: string;
  name: string;
  start: number;
  end: number;
  progress?: number; // 0–1
  group?: string;
  color: SeriesColor;
  milestone: boolean;
  dependsOn: number[]; // indices
}

export interface ResolvedGanttSpec {
  title?: string;
  subtitle?: string;
  tasks: ResolvedTask[];
  groups: { name: string; color: SeriesColor }[];
  today: number | null;
  markers: { date: number; label?: string }[];
  labels: GanttLabels;
  range: [number, number];
  emptyMessage: string;
}

export function normalizeGanttSpec(input: unknown): Normalized<ResolvedGanttSpec> {
  const warnings: string[] = [];
  const raw = isObject(input) ? input : {};
  if (!isObject(input)) warnings.push("Spec was not an object; rendering an empty chart.");
  if (isObject(input) && !Array.isArray(raw.tasks)) warnings.push("Spec has no `tasks`; rendering an empty chart.");

  type Draft = Omit<ResolvedTask, "color" | "dependsOn"> & { deps: string[] };
  const drafts: Draft[] = toArray(raw.tasks).flatMap((t, i) => {
    if (!isObject(t)) return [];
    const name = optionalString(t.name ?? t.title) ?? `Task ${i + 1}`;
    let start = toDate(t.start, `tasks[${i}].start`, warnings);
    if (start === null) {
      warnings.push(`tasks[${i}] ("${name}") has no valid start date; dropped.`);
      return [];
    }
    let end = toDate(t.end, `tasks[${i}].end`, warnings);
    const dur = optionalNumber(t.durationDays);
    if (end === null && dur !== undefined) end = start + Math.max(0, dur) * DAY;
    if (end !== null && end < start) {
      warnings.push(`tasks[${i}] ("${name}") ends before it starts; dates swapped.`);
      [start, end] = [end, start];
    }
    const milestone = t.milestone === true || end === null || end === start;
    let progress = optionalNumber(t.progress);
    if (progress !== undefined) {
      if (progress > 1) progress /= 100;
      progress = Math.min(1, Math.max(0, progress));
    }
    const resolvedEnd = milestone ? start : end!;
    return [
      {
        id: optionalString(t.id) ?? name,
        name,
        start,
        end: resolvedEnd,
        progress: milestone ? undefined : progress,
        group: optionalString(t.group),
        milestone,
        deps: toArray(t.dependsOn).map(String),
      },
    ];
  });

  const ids = uniqueNames(drafts.map((d) => d.id), warnings, "task id");
  drafts.forEach((d, i) => (d.id = ids[i]));
  const byKey = new Map<string, number>();
  drafts.forEach((d, i) => {
    byKey.set(d.id, i);
    if (!byKey.has(d.name)) byKey.set(d.name, i);
  });

  // Group colours, in order of first appearance; pins win.
  const groupNames = [...new Set(drafts.map((d) => d.group).filter((g): g is string => !!g))];
  const pinsRaw = isObject(raw.groupColors) ? raw.groupColors : {};
  const pins = groupNames.map((g) => pickColor(pinsRaw[g], `groupColors.${g}`, warnings));
  const groupColors = assignColors(pins);
  if (groupNames.length > MAX_COLORED_SERIES) warnings.push(`${groupNames.length} groups; groups after the 4th are grey.`);
  const colorOf = new Map(groupNames.map((g, i) => [g, groupColors[i]]));

  const tasks: ResolvedTask[] = drafts.map((d, i) => ({
    id: d.id,
    name: d.name,
    start: d.start,
    end: d.end,
    progress: d.progress,
    group: d.group,
    milestone: d.milestone,
    color: d.group ? colorOf.get(d.group)! : "purple",
    dependsOn: d.deps.flatMap((k) => {
      const j = byKey.get(k);
      if (j === undefined || j === i) {
        warnings.push(`"${d.name}" depends on unknown task "${k}"; ignored.`);
        return [];
      }
      return [j];
    }),
  }));

  const markers = toArray(raw.markers).flatMap((m, i) => {
    const date = isObject(m) ? toDate(m.date, `markers[${i}].date`, warnings) : null;
    return date === null ? [] : [{ date, label: isObject(m) ? optionalString(m.label) : undefined }];
  });

  // Range: tasks + markers, padded a little; explicit range wins.
  const times = [...tasks.flatMap((t) => [t.start, t.end]), ...markers.map((m) => m.date)];
  let lo = times.length ? Math.min(...times) : Date.now();
  let hi = times.length ? Math.max(...times) : Date.now() + 30 * DAY;
  const pad = Math.max(DAY, (hi - lo) * 0.03);
  lo -= pad;
  hi += pad;
  const rr = isObject(raw.range) ? raw.range : {};
  lo = toDate(rr.start, "range.start", warnings) ?? lo;
  hi = toDate(rr.end, "range.end", warnings) ?? hi;

  const now = new Date();
  const todayUtc = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  let today: number | null = null;
  if (typeof raw.today === "string") today = toDate(raw.today, "today", warnings);
  else if (raw.today !== false) today = todayUtc >= lo && todayUtc <= hi ? todayUtc : null;
  if (raw.today === true && (todayUtc < lo || todayUtc > hi)) {
    lo = Math.min(lo, todayUtc - DAY);
    hi = Math.max(hi, todayUtc + DAY);
    today = todayUtc;
  }

  return {
    warnings,
    spec: {
      title: optionalString(raw.title),
      subtitle: optionalString(raw.subtitle),
      tasks,
      groups: groupNames.map((g, i) => ({ name: g, color: groupColors[i] })),
      today,
      markers,
      labels: pickEnum<GanttLabels>(raw.labels, ["auto", "none", "progress", "duration", "dates"], "auto", "labels", warnings),
      range: [lo, hi],
      emptyMessage: optionalString(raw.emptyMessage) ?? "No tasks to show yet.",
    },
  };
}
