import { useChartWarnings } from "../shared/hooks";
import { anchorAbove } from "../shared/layout";
import type { Plot } from "../shared/layout";
import { FONT, thinTicks } from "../shared/layout";
import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { CartesianAxes, ReferenceRule } from "../shared/axes";
import { ChartFrame } from "../shared/chart-frame";
import { CHART_TOKENS, SERIES_COLORS } from "../shared/palette";
import { linear, makeFormatter, measureText, niceTicks } from "../shared/scale";
import { ChartTooltip } from "../shared/tooltip";
import { normalizeHistogramSpec } from "./spec";
import type { HistogramSpec, ResolvedHistogramSpec } from "./spec";

export interface HistogramProps {
  spec: HistogramSpec | unknown;
  className?: string;
  loading?: boolean;
  onWarnings?: (warnings: string[]) => void;
  onBinClick?: (bin: { start: number; end: number; count: number }) => void;
}

const GAP = 2;
const RADIUS = 4;

export function Histogram({ spec: input, className = "", loading = false, onWarnings, onBinClick }: HistogramProps) {
  const { spec, warnings } = useMemo(() => normalizeHistogramSpec(input), [input]);
  useChartWarnings("Histogram", warnings, onWarnings);
  const [active, setActive] = useState<number | null>(null);
  const hitRefs = useRef<(SVGRectElement | null)[]>([]);

  const isEmpty = spec.bins.length === 0 || spec.total === 0;
  const fmt = useMemo(() => {
    const maxAbs = Math.max(0, ...spec.bins.map((b) => Math.max(Math.abs(b.start), Math.abs(b.end))));
    return makeFormatter(spec.valueFormat, maxAbs);
  }, [spec]);
  const countFmt = new Intl.NumberFormat();
  const range = (i: number) => `${fmt(spec.bins[i].start)} – ${fmt(spec.bins[i].end)}`;
  const share = (c: number) => (spec.total ? `${Math.round((c / spec.total) * 100)}%` : "0%");

  const subtitle =
    spec.subtitle ??
    (spec.stats ? `${countFmt.format(spec.stats.n)} ${spec.countLabel.toLowerCase()} · median ${fmt(spec.stats.median)}` : undefined);

  return (
    <ChartFrame
      title={spec.title}
      subtitle={subtitle}
      className={className}
      loading={loading}
      empty={isEmpty}
      emptyMessage={spec.emptyMessage}
      emptyHeight={spec.height}
      table={{
        columns: [spec.xAxis.label ?? "Range", spec.countLabel, "Share"],
        rows: spec.bins.map((b, i) => [range(i), countFmt.format(b.count), share(b.count)]),
        numeric: [1, 2],
      }}
    >
      {(width) => {
        const g = layout(spec, width, fmt);
        const onKey = (e: KeyboardEvent<SVGRectElement>, i: number) => {
          const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (step) {
            e.preventDefault();
            hitRefs.current[(i + step + g.bars.length) % g.bars.length]?.focus();
          } else if (onBinClick && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            onBinClick(spec.bins[i]);
          } else if (e.key === "Escape") e.currentTarget.blur();
        };
        return (
          <>
            <svg width={width} height={g.height} className="block overflow-visible select-none" style={{ fontSize: FONT }} role="group" aria-label={`${spec.title ?? "Histogram"}. Use arrow keys to move between bins.`}>
              <CartesianAxes
                plot={g.plot}
                height={g.height}
                xTicks={spec.xAxis.show ? g.xTicks : []}
                yTicks={spec.yAxis.show ? g.yTicks : []}
                yGrid={spec.yAxis.gridlines}
                xTitle={spec.xAxis.label}
                yTitle={spec.yAxis.label ?? spec.countLabel}
              />
              {active !== null && <rect x={g.bars[active].x0 - 1} y={g.plot.top} width={g.bars[active].x1 - g.bars[active].x0 + 2} height={g.plot.height} rx={4} fill={CHART_TOKENS.hoverWash} opacity={0.7} />}
              {g.bars.map((b, i) => (
                <path
                  key={i}
                  d={b.path}
                  fill={SERIES_COLORS[spec.color].fill}
                  opacity={b.dim ? 0.35 : 1}
                  className="motion-safe:transition-[d,opacity] motion-safe:duration-300"
                  style={{ filter: active === i ? "brightness(1.15)" : undefined }}
                />
              ))}
              <line x1={g.plot.left} x2={g.plot.left + g.plot.width} y1={g.plot.top + g.plot.height} y2={g.plot.top + g.plot.height} stroke={CHART_TOKENS.baseline} shapeRendering="crispEdges" />
              {g.rules.map((r, i) => (
                <ReferenceRule key={i} orientation="vertical" pos={r.pos} plot={g.plot} label={r.label || undefined} labelOffset={r.offset} />
              ))}
              {g.bars.map((b, i) => (
                <rect
                  key={`hit${i}`}
                  ref={(el) => {
                    hitRefs.current[i] = el;
                  }}
                  x={b.x0 - GAP / 2}
                  y={g.plot.top}
                  width={b.x1 - b.x0 + GAP}
                  height={g.plot.height}
                  fill="transparent"
                  tabIndex={0}
                  role={onBinClick ? "button" : "img"}
                  aria-label={`${range(i)}: ${countFmt.format(spec.bins[i].count)} ${spec.countLabel.toLowerCase()} (${share(spec.bins[i].count)})`}
                  className={["outline-none", onBinClick ? "cursor-pointer" : ""].join(" ")}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive((a) => (a === i ? null : a))}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive((a) => (a === i ? null : a))}
                  onClick={() => onBinClick?.(spec.bins[i])}
                  onKeyDown={(e) => onKey(e, i)}
                />
              ))}
            </svg>
            {active !== null && (
              <ChartTooltip
                {...anchorAbove((g.bars[active].x0 + g.bars[active].x1) / 2, g.bars[active].top, width)}
                title={range(active)}
                rows={[{ color: spec.color, value: countFmt.format(spec.bins[active].count), extra: `(${share(spec.bins[active].count)})`, label: spec.countLabel }]}
              />
            )}
          </>
        );
      }}
    </ChartFrame>
  );
}

export default Histogram;

function layout(spec: ResolvedHistogramSpec, width: number, fmt: (v: number) => string) {
  const bins = spec.bins;
  const maxCount = Math.max(...bins.map((b) => b.count), spec.yAxis.max ?? 0);
  // Counts are whole numbers: never draw a 0.5 tick.
  let yTickValues = niceTicks(0, maxCount, spec.yAxis.tickCount);
  if (maxCount <= 5) yTickValues = Array.from({ length: Math.max(1, maxCount) + 1 }, (_, i) => i);
  yTickValues = yTickValues.filter((v) => Number.isInteger(v));
  const yMax = yTickValues[yTickValues.length - 1] || 1;
  const countFmt = makeFormatter({}, yMax);
  const yTexts = yTickValues.map(countFmt);
  const tickW = Math.max(...yTexts.map((t) => measureText(t)));

  const ruleCount = spec.markers.length + spec.referenceLines.length;
  const top = ruleCount > 1 ? 36 : ruleCount ? 22 : 12;
  const bottom = (spec.xAxis.show ? 28 : 8) + (spec.xAxis.label ? 18 : 0);
  const left = (spec.yAxis.show ? tickW + 10 : 4) + 20;
  const right = 16;
  const plot: Plot = { left, top, width: width - left - right, height: spec.height - top - bottom };

  const lo = bins[0].start;
  const hi = bins[bins.length - 1].end;
  const x = linear(lo, hi, plot.left, plot.left + plot.width);
  const y = linear(0, yMax, plot.top + plot.height, plot.top);

  const hr = spec.highlightRange;
  const bars = bins.map((b) => {
    const x0 = x(b.start) + GAP / 2;
    const x1 = Math.max(x0 + 1, x(b.end) - GAP / 2);
    const base = y(0);
    const top = y(b.count);
    const r = Math.min(RADIUS, (x1 - x0) / 2, base - top);
    const path =
      b.count === 0
        ? ""
        : `M${x0},${base}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x1 - r}Q${x1},${top} ${x1},${top + r}V${base}Z`;
    const dim = hr ? b.end <= hr.from || b.start >= hr.to : false;
    return { x0, x1, top, path, dim };
  });

  // X ticks at bin edges, thinned so labels never collide.
  const edges = [...bins.map((b) => b.start), hi];
  const xTicks = thinTicks(
    edges.map((v) => ({ pos: x(v), text: fmt(v) })),
    (t) => measureText(t),
  );

  const rules: { pos: number; label: string; offset: number }[] = [];
  if (spec.stats) {
    for (const m of spec.markers) {
      const v = spec.stats[m];
      rules.push({ pos: x(v), label: `${m === "mean" ? "Mean" : "Median"} · ${fmt(v)}`, offset: 0 });
    }
  }
  for (const r of spec.referenceLines) {
    if (r.value >= lo && r.value <= hi) rules.push({ pos: x(r.value), label: r.label ? `${r.label} · ${fmt(r.value)}` : fmt(r.value), offset: 0 });
  }
  // Labels too close to their neighbour move up a row (a third collision drops the label).
  rules.sort((a, b) => a.pos - b.pos);
  rules.forEach((r, i) => {
    const prev = rules[i - 1];
    if (!prev || r.pos - prev.pos >= (measureText(r.label, 11) + measureText(prev.label, 11)) / 2 + 8) return;
    if (prev.offset === 0) r.offset = 14;
    else r.label = "";
  });

  return {
    height: spec.height,
    plot,
    bars,
    xTicks,
    yTicks: yTickValues.map((v, i) => ({ pos: y(v), text: yTexts[i] })),
    rules,
  };
}
