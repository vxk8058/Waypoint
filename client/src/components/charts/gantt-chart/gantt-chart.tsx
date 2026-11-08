import { useChartWarnings } from "../shared/hooks";
import { anchorAbove } from "../shared/layout";
import { FONT, HALO, thinTicks } from "../shared/layout";
import { useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { ChartFrame } from "../shared/chart-frame";
import { CHART_TOKENS, SERIES_COLORS } from "../shared/palette";
import { linear, measureText, truncateToWidth } from "../shared/scale";
import { DAY, daysBetween, formatDate, timeTicks } from "../shared/time";
import { ChartTooltip } from "../shared/tooltip";
import { normalizeGanttSpec } from "./spec";
import type { GanttChartSpec, ResolvedGanttSpec, ResolvedTask } from "./spec";

export interface GanttChartProps {
  spec: GanttChartSpec | unknown;
  className?: string;
  loading?: boolean;
  onWarnings?: (warnings: string[]) => void;
  onTaskClick?: (task: { id: string; name: string; start: string; end: string; progress?: number; group?: string }) => void;
}

const ROW = 36;
const BAR = 16;
const AXIS_H = 44; // room for the Today/marker tags above the tick labels

export function GanttChart({ spec: input, className = "", loading = false, onWarnings, onTaskClick }: GanttChartProps) {
  const { spec, warnings } = useMemo(() => normalizeGanttSpec(input), [input]);
  useChartWarnings("GanttChart", warnings, onWarnings);
  const [active, setActive] = useState<number | null>(null);
  const hitRefs = useRef<(SVGRectElement | null)[]>([]);
  const uid = useId().replace(/:/g, "");

  const duration = (t: ResolvedTask) => {
    const d = daysBetween(t.start, t.end);
    return `${d} day${d === 1 ? "" : "s"}`;
  };
  const dates = (t: ResolvedTask) => (t.milestone ? formatDate(t.start) : `${formatDate(t.start)} – ${formatDate(t.end)}`);
  const pct = (p?: number) => (p === undefined ? "—" : `${Math.round(p * 100)}%`);
  const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
  const fire = (i: number) => {
    const t = spec.tasks[i];
    onTaskClick?.({ id: t.id, name: t.name, start: iso(t.start), end: iso(t.end), progress: t.progress, group: t.group });
  };

  return (
    <ChartFrame
      title={spec.title}
      subtitle={spec.subtitle}
      className={className}
      loading={loading}
      empty={spec.tasks.length === 0}
      emptyMessage={spec.emptyMessage}
      emptyHeight={160}
      legend={spec.groups.length > 1 ? { items: spec.groups.map((g) => ({ name: g.name, color: g.color })) } : null}
      table={{
        columns: ["Task", ...(spec.groups.length ? ["Group"] : []), "Start", "End", "Duration", "Progress"],
        rows: spec.tasks.map((t) => [
          t.name,
          ...(spec.groups.length ? [t.group ?? "—"] : []),
          formatDate(t.start),
          t.milestone ? "—" : formatDate(t.end),
          t.milestone ? "Milestone" : duration(t),
          pct(t.progress),
        ]),
        numeric: spec.groups.length ? [4, 5] : [3, 4],
      }}
    >
      {(width) => {
        const g = layout(spec, width);
        const onKey = (e: KeyboardEvent<SVGRectElement>, i: number) => {
          const step = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
          if (step) {
            e.preventDefault();
            hitRefs.current[(i + step + spec.tasks.length) % spec.tasks.length]?.focus();
          } else if (onTaskClick && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            fire(i);
          } else if (e.key === "Escape") e.currentTarget.blur();
        };
        const at = active !== null ? spec.tasks[active] : null;
        const ab = active !== null ? g.bars[active] : null;

        return (
          <>
            <svg width={width} height={g.height} className="block overflow-visible select-none" style={{ fontSize: FONT }} role="group" aria-label={`${spec.title ?? "Gantt chart"}. ${spec.tasks.length} tasks. Use up and down arrow keys to move between tasks.`}>
              <defs>
                <marker id={`${uid}-arrow`} viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M0,0L6,3L0,6Z" fill={CHART_TOKENS.textMuted} />
                </marker>
                {g.bars.map((b, i) => (
                  <clipPath key={i} id={`${uid}-c${i}`}>
                    <rect x={b.x0} y={b.y} width={b.x1 - b.x0} height={BAR} rx={4} />
                  </clipPath>
                ))}
              </defs>

              {/* Time axis on top, hairline grid down the rows */}
              {g.ticks.map((t) => (
                <g key={t.pos}>
                  <line x1={t.pos} x2={t.pos} y1={AXIS_H - 4} y2={g.height} stroke={CHART_TOKENS.grid} shapeRendering="crispEdges" />
                  <text x={t.pos + 4} y={AXIS_H - 12} fill={CHART_TOKENS.textMuted}>
                    {t.text}
                  </text>
                </g>
              ))}
              <line x1={g.left} x2={width} y1={AXIS_H - 4} y2={AXIS_H - 4} stroke={CHART_TOKENS.baseline} shapeRendering="crispEdges" />

              {/* Row wash on hover */}
              {active !== null && <rect x={0} y={AXIS_H + active * ROW} width={width} height={ROW} rx={6} fill={CHART_TOKENS.hoverWash} opacity={0.7} />}

              {/* Task names */}
              {spec.tasks.map((t, i) => (
                <text key={t.id} x={0} y={AXIS_H + i * ROW + ROW / 2 + 4} fill={active === i ? CHART_TOKENS.textPrimary : CHART_TOKENS.textSecondary}>
                  <title>{t.name}</title>
                  {g.names[i]}
                </text>
              ))}

              {/* Dependencies: elbow connectors from a task's end to its successor's start */}
              {g.links.map((d, i) => (
                <path key={i} d={d} fill="none" stroke={CHART_TOKENS.textMuted} strokeWidth={1} markerEnd={`url(#${uid}-arrow)`} opacity={0.8} />
              ))}

              {/* Bars and milestones */}
              {spec.tasks.map((t, i) => {
                const b = g.bars[i];
                const fill = SERIES_COLORS[t.color].fill;
                if (t.milestone) {
                  const cy = b.y + BAR / 2;
                  const s = 7;
                  return <path key={t.id} d={`M${b.x0},${cy - s}L${b.x0 + s},${cy}L${b.x0},${cy + s}L${b.x0 - s},${cy}Z`} fill={fill} stroke="var(--color-surface)" strokeWidth={2} />;
                }
                const hasProgress = t.progress !== undefined && t.progress < 1;
                return (
                  <g key={t.id} style={{ filter: active === i ? "brightness(1.15)" : undefined }}>
                    <rect x={b.x0} y={b.y} width={b.x1 - b.x0} height={BAR} rx={4} fill={fill} opacity={hasProgress ? 0.32 : 1} />
                    {hasProgress && <rect x={b.x0} y={b.y} width={(b.x1 - b.x0) * t.progress!} height={BAR} fill={fill} clipPath={`url(#${uid}-c${i})`} />}
                  </g>
                );
              })}

              {g.labels.map((l, i) =>
                l ? (
                  <text key={i} x={l.x} y={l.y} fill={CHART_TOKENS.textSecondary} fontSize={11} {...HALO} pointerEvents="none">
                    {l.text}
                  </text>
                ) : null,
              )}

              {/* Today + dated markers */}
              {g.rules.map((r, i) => (
                <g key={i} pointerEvents="none">
                  <line x1={r.x} x2={r.x} y1={AXIS_H - 4} y2={g.height} stroke={r.today ? CHART_TOKENS.textPrimary : CHART_TOKENS.reference} strokeWidth={1} strokeDasharray={r.today ? undefined : "4 3"} shapeRendering="crispEdges" />
                  <rect x={r.x - r.w / 2 - 4} y={2} width={r.w + 8} height={16} rx={4} fill={r.today ? "var(--color-blue-grey-050)" : "var(--color-surface-raised)"} />
                  <text x={r.x} y={14} textAnchor="middle" fontSize={11} fontWeight={600} fill={r.today ? "var(--color-canvas)" : CHART_TOKENS.textSecondary}>
                    {r.label}
                  </text>
                </g>
              ))}

              {/* Hit targets: the whole row */}
              {spec.tasks.map((t, i) => (
                <rect
                  key={`hit${t.id}`}
                  ref={(el) => {
                    hitRefs.current[i] = el;
                  }}
                  x={0}
                  y={AXIS_H + i * ROW}
                  width={width}
                  height={ROW}
                  fill="transparent"
                  tabIndex={0}
                  role={onTaskClick ? "button" : "img"}
                  aria-label={`${t.name}: ${dates(t)}${t.milestone ? ", milestone" : `, ${duration(t)}`}${t.progress !== undefined ? `, ${pct(t.progress)} complete` : ""}`}
                  className={["outline-none", onTaskClick ? "cursor-pointer" : ""].join(" ")}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive((a) => (a === i ? null : a))}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive((a) => (a === i ? null : a))}
                  onClick={() => fire(i)}
                  onKeyDown={(e) => onKey(e, i)}
                />
              ))}
            </svg>

            {at && ab && (
              <ChartTooltip
                {...anchorAbove((ab.x0 + ab.x1) / 2, ab.y - 2, width)}
                title={at.name}
                rows={[
                  { color: at.color, value: dates(at), label: at.group },
                  ...(at.milestone ? [{ value: "Milestone" }] : [{ value: duration(at), label: "Duration" }]),
                  ...(at.progress !== undefined ? [{ value: pct(at.progress), label: "Complete" }] : []),
                  ...(at.dependsOn.length ? [{ value: at.dependsOn.map((j) => spec.tasks[j].name).join(", "), label: "After" }] : []),
                ]}
              />
            )}
          </>
        );
      }}
    </ChartFrame>
  );
}

export default GanttChart;

function layout(spec: ResolvedGanttSpec, width: number) {
  const nameW = Math.min(Math.max(...spec.tasks.map((t) => measureText(t.name))), width * 0.3);
  const left = nameW + 16;
  const right = 12;
  const [t0, t1] = spec.range;
  const x = linear(t0, t1, left, width - right);
  const height = AXIS_H + spec.tasks.length * ROW + 4;

  const ticks = thinTicks(
    timeTicks(t0, t1, Math.max(2, Math.floor((width - left) / 44))).map((t) => ({ pos: x(t.value), text: t.text })),
    (t) => measureText(t) + 8, // labels sit to the right of their tick
  );

  const bars = spec.tasks.map((t, i) => {
    const y = AXIS_H + i * ROW + (ROW - BAR) / 2;
    const x0 = Math.max(left, x(t.start));
    const x1 = Math.min(width - right, Math.max(x0 + 4, x(t.end)));
    return { x0, x1, y };
  });

  const mode = spec.labels === "auto" ? (spec.tasks.some((t) => t.progress !== undefined) ? "progress" : "none") : spec.labels;
  const labels = spec.tasks.map((t, i) => {
    if (mode === "none") return null;
    let text = "";
    if (t.milestone) text = formatDate(t.start).replace(/, \d{4}$/, "");
    else if (mode === "progress") text = t.progress === undefined ? "" : `${Math.round(t.progress * 100)}%`;
    else if (mode === "duration") text = `${daysBetween(t.start, t.end)}d`;
    else text = `${formatDate(t.start).replace(/, \d{4}$/, "")} – ${formatDate(t.end).replace(/, \d{4}$/, "")}`;
    if (!text) return null;
    const b = bars[i];
    const after = (t.milestone ? b.x0 + 10 : b.x1 + 6) + measureText(text, 11) < width;
    return { x: after ? (t.milestone ? b.x0 + 10 : b.x1 + 6) : b.x0 - 6 - measureText(text, 11) - (t.milestone ? 4 : 0), y: b.y + BAR / 2 + 4, text };
  });

  const links: string[] = [];
  spec.tasks.forEach((t, i) => {
    for (const j of t.dependsOn) {
      const from = bars[j];
      const to = bars[i];
      const fx = spec.tasks[j].milestone ? from.x0 + 7 : from.x1;
      const fy = from.y + BAR / 2;
      const tx = spec.tasks[i].milestone ? to.x0 - 8 : to.x0 - 1;
      const ty = to.y + BAR / 2;
      if (tx - fx >= 12) {
        const mid = fx + 6;
        links.push(`M${fx},${fy}H${mid}V${ty}H${tx}`);
      } else {
        // Successor starts before the predecessor ends: route around through the row gap.
        const gapY = ty > fy ? to.y - (ROW - BAR) / 2 : to.y + BAR + (ROW - BAR) / 2;
        links.push(`M${fx},${fy}H${fx + 6}V${gapY}H${tx - 8}V${ty}H${tx}`);
      }
    }
  });

  const rules: { x: number; label: string; w: number; today: boolean }[] = [];
  const addRule = (date: number, label: string, today: boolean) => {
    if (date < t0 || date > t1) return;
    rules.push({ x: x(date + (today ? DAY / 2 : 0)), label, w: measureText(label, 11, 600), today });
  };
  for (const m of spec.markers) addRule(m.date, m.label ?? formatDate(m.date), false);
  if (spec.today !== null) addRule(spec.today, "Today", true);

  return {
    height,
    left,
    ticks,
    bars,
    names: spec.tasks.map((t) => truncateToWidth(t.name, nameW)),
    labels,
    links,
    rules,
  };
}
