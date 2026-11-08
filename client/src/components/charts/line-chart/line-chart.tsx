import { useChartWarnings, useHiddenSeries } from "../shared/hooks";
import { anchorBeside } from "../shared/layout";
import type { Plot, Tick } from "../shared/layout";
import { FONT, HALO, thinTicks } from "../shared/layout";
import { useMemo, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { CartesianAxes, ReferenceRule } from "../shared/axes";
import { ChartFrame } from "../shared/chart-frame";
import { CHART_TOKENS, MAX_COLORED_SERIES, SERIES_COLORS } from "../shared/palette";
import { linear, makeFormatter, measureText, niceTicks } from "../shared/scale";
import { formatDate, timeTicks } from "../shared/time";
import { ChartTooltip } from "../shared/tooltip";
import { normalizeLineChartSpec } from "./spec";
import type { LineChartSpec, ResolvedLineChartSpec, ResolvedLineSeries } from "./spec";

export interface LineChartProps {
  spec: LineChartSpec | unknown;
  className?: string;
  loading?: boolean;
  onWarnings?: (warnings: string[]) => void;
  onPointClick?: (event: { x: string; index: number; values: { series: string; value: number | null }[] }) => void;
}

type Pt = [number, number];

export function LineChart({ spec: input, className = "", loading = false, onWarnings, onPointClick }: LineChartProps) {
  const { spec, warnings } = useMemo(() => normalizeLineChartSpec(input), [input]);
  useChartWarnings("LineChart", warnings, onWarnings);

  const [hidden, toggle] = useHiddenSeries(spec.series.length);
  const [active, setActive] = useState<number | null>(null);
  const visible = useMemo(() => spec.series.filter((s) => !hidden.has(s.name)), [spec, hidden]);

  const isEmpty = spec.xs.length === 0 || visible.every((s) => s.values.every((v) => v === null));
  const fmt = useMemo(() => {
    const maxAbs = Math.max(0, ...spec.series.flatMap((s) => s.values.map((v) => Math.abs(v ?? 0))));
    return makeFormatter(spec.valueFormat, maxAbs);
  }, [spec]);
  const xText = (i: number) => (spec.xType === "time" ? formatDate(spec.xs[i]) : spec.xLabels[i]);
  const cell = (v: number | null | undefined) => (v === null || v === undefined ? "—" : fmt(v));
  const hasBand = visible.some((s) => s.band);

  return (
    <ChartFrame
      title={spec.title}
      subtitle={spec.subtitle}
      className={className}
      loading={loading}
      empty={isEmpty}
      emptyMessage={spec.emptyMessage}
      emptyHeight={spec.height}
      legend={
        spec.legend.show
          ? { shape: "line", items: spec.series.map((s) => ({ name: s.name, color: colorOf(spec, s, spec.series.indexOf(s)), off: hidden.has(s.name) })), onToggle: toggle }
          : null
      }
      table={{
        columns: [
          spec.xAxis.label ?? (spec.xType === "time" ? "Date" : "X"),
          ...visible.flatMap((s) => (s.band ? [s.name, `${s.name} low`, `${s.name} high`] : [s.name])),
        ],
        rows: spec.xs.map((_, i) => [
          xText(i) + (spec.forecastIndex >= 0 && i >= spec.forecastIndex ? " (projected)" : ""),
          ...visible.flatMap((s) => (s.band ? [cell(s.values[i]), cell(s.band.lower[i]), cell(s.band.upper[i])] : [cell(s.values[i])])),
        ]),
        numeric: Array.from({ length: visible.length * (hasBand ? 3 : 1) }, (_, i) => i + 1),
      }}
    >
      {(width) => {
        const g = layout(spec, visible, width);
        const move = (e: PointerEvent<SVGRectElement>) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const px = e.clientX - rect.left + g.plot.left;
          let best = 0;
          g.xPx.forEach((x, i) => {
            if (Math.abs(x - px) < Math.abs(g.xPx[best] - px)) best = i;
          });
          setActive(best);
        };
        const key = (e: KeyboardEvent<SVGRectElement>) => {
          const n = spec.xs.length;
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            setActive((a) => ((a ?? (e.key === "ArrowRight" ? -1 : n)) + (e.key === "ArrowRight" ? 1 : -1) + n) % n);
          } else if (e.key === "Escape") setActive(null);
          else if ((e.key === "Enter" || e.key === " ") && active !== null) {
            e.preventDefault();
            fire(active);
          }
        };
        const fire = (i: number) =>
          onPointClick?.({ x: spec.xLabels[i], index: i, values: visible.map((s) => ({ series: s.name, value: s.values[i] })) });

        return (
          <>
            <svg width={width} height={g.height} className="block overflow-visible select-none" style={{ fontSize: FONT }} aria-hidden>
              <CartesianAxes
                plot={g.plot}
                height={g.height}
                xTicks={spec.xAxis.show ? g.xTicks : []}
                yTicks={spec.yAxis.show ? g.yTicks : []}
                yGrid={spec.yAxis.gridlines}
                xTitle={spec.xAxis.label}
                yTitle={spec.yAxis.label}
              />

              {/* Forecast region: a faint wash and label so projections never pass for actuals */}
              {g.forecastX !== null && (
                <g pointerEvents="none">
                  <rect x={g.forecastX} y={g.plot.top} width={g.plot.left + g.plot.width - g.forecastX} height={g.plot.height} fill={CHART_TOKENS.hoverWash} opacity={0.35} />
                  <text x={g.forecastX + 6} y={g.plot.top + 12} fill={CHART_TOKENS.textMuted} fontSize={11}>
                    Projected
                  </text>
                </g>
              )}

              {g.zeroY !== null && <line x1={g.plot.left} x2={g.plot.left + g.plot.width} y1={g.zeroY} y2={g.zeroY} stroke={CHART_TOKENS.baseline} shapeRendering="crispEdges" />}

              {g.lines.map((l) => (
                <g key={l.name} opacity={l.dim ? 0.55 : 1}>
                  {l.bands.map((d, i) => (
                    <path key={`b${i}`} d={d} fill={l.fill} opacity={0.16} />
                  ))}
                  {l.areas.map((d, i) => (
                    <path key={`a${i}`} d={d} fill={l.fill} opacity={0.1} />
                  ))}
                  <path d={l.solid} fill="none" stroke={l.fill} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                  <path d={l.dashed} fill="none" stroke={l.fill} strokeWidth={2} strokeDasharray="5 4" strokeLinecap="round" />
                  {l.markers.map(([x, y], i) => (
                    <circle key={i} cx={x} cy={y} r={4} fill={l.fill} stroke="var(--color-surface)" strokeWidth={2} />
                  ))}
                </g>
              ))}

              {spec.referenceLines.map((r, i) =>
                r.value >= g.d0 && r.value <= g.d1 ? (
                  <ReferenceRule key={i} orientation="horizontal" align="start" pos={g.y(r.value)} plot={g.plot} label={r.label ? `${r.label} · ${fmt(r.value)}` : undefined} />
                ) : null,
              )}

              {g.valueLabels.map((l, i) => (
                <text key={i} x={l.x} y={l.y} textAnchor={l.anchor} fill={CHART_TOKENS.textPrimary} fontWeight={600} {...HALO}>
                  {l.text}
                </text>
              ))}
              {g.endLabels.map((l) => (
                <text key={l.text} x={l.x} y={l.y + 4} fill={CHART_TOKENS.textSecondary} {...HALO}>
                  {l.text}
                </text>
              ))}

              {/* Crosshair */}
              {active !== null && (
                <g pointerEvents="none">
                  <line x1={g.xPx[active]} x2={g.xPx[active]} y1={g.plot.top} y2={g.plot.top + g.plot.height} stroke={CHART_TOKENS.textMuted} strokeWidth={1} shapeRendering="crispEdges" />
                  {g.lines.map((l) => {
                    const v = l.series.values[active];
                    return v === null ? null : <circle key={l.name} cx={g.xPx[active]} cy={g.y(v)} r={4.5} fill={l.fill} stroke="var(--color-surface)" strokeWidth={2} />;
                  })}
                </g>
              )}
            </svg>

            {/* Hit layer: the whole plot; the crosshair snaps to the nearest x */}
            <svg width={width} height={g.height} className="absolute inset-0 overflow-visible" role="group" aria-label={`${spec.title ?? "Line chart"}. Use left and right arrow keys to read values.`}>
              <rect
                x={g.plot.left}
                y={g.plot.top}
                width={g.plot.width}
                height={g.plot.height}
                fill="transparent"
                tabIndex={0}
                aria-label={active !== null ? `${xText(active)}: ${visible.map((s) => `${s.name} ${cell(s.values[active])}`).join(", ")}` : "Chart values"}
                className={["outline-none focus-visible:stroke-purple-400", onPointClick ? "cursor-pointer" : "cursor-crosshair"].join(" ")}
                onPointerMove={move}
                onPointerLeave={() => setActive(null)}
                onBlur={() => setActive(null)}
                onKeyDown={key}
                onClick={() => active !== null && fire(active)}
              />
            </svg>

            {active !== null && (
              <ChartTooltip
                {...anchorBeside(g.xPx[active], g.plot.top + g.plot.height * 0.3, width)}
                title={xText(active) + (spec.forecastIndex >= 0 && active >= spec.forecastIndex ? " · projected" : "")}
                rows={g.lines.map((l) => ({
                  color: l.color,
                  value: cell(l.series.values[active]),
                  label: l.name,
                  extra: l.series.band ? `(${cell(l.series.band.lower[active])} – ${cell(l.series.band.upper[active])})` : undefined,
                }))}
              />
            )}
          </>
        );
      }}
    </ChartFrame>
  );
}

export default LineChart;

// ---------------------------------------------------------------------------

function colorOf(spec: ResolvedLineChartSpec, s: ResolvedLineSeries, index: number) {
  if (spec.highlight.length && !spec.highlight.includes(s.name)) return "neutral" as const;
  return index < MAX_COLORED_SERIES || s.color !== "neutral" ? s.color : "neutral";
}

function layout(spec: ResolvedLineChartSpec, visible: ResolvedLineSeries[], width: number) {
  const n = spec.xs.length;

  // ---- y domain ----
  let lo = Infinity;
  let hi = -Infinity;
  const see = (v: number | null | undefined) => {
    if (v === null || v === undefined) return;
    lo = Math.min(lo, v);
    hi = Math.max(hi, v);
  };
  visible.forEach((s) => {
    s.values.forEach(see);
    s.band?.lower.forEach(see);
    s.band?.upper.forEach(see);
  });
  spec.referenceLines.forEach((r) => see(r.value));
  see(spec.yAxis.min);
  see(spec.yAxis.max);
  if (!Number.isFinite(lo)) [lo, hi] = [0, 1];
  const yTickValues = niceTicks(lo, hi, spec.yAxis.tickCount, spec.yAxis.includeZero);
  const d0 = yTickValues[0];
  const d1 = yTickValues[yTickValues.length - 1];
  const axisFmt = makeFormatter(spec.valueFormat, Math.max(Math.abs(d0), Math.abs(d1)));
  const valueFmt = makeFormatter(spec.valueFormat, Math.max(Math.abs(lo), Math.abs(hi)));
  const yTexts = yTickValues.map(axisFmt);
  const tickW = Math.max(...yTexts.map((t) => measureText(t)));

  const top = 16;
  const bottom = (spec.xAxis.show ? 28 : 8) + (spec.xAxis.label ? 18 : 0);
  const height = spec.height;
  const plotH = height - top - bottom;
  const y = linear(d0, d1, top + plotH, top);

  // ---- end labels (decided before x so the right margin can make room) ----
  const lastIdx = visible.map((s) => {
    for (let i = n - 1; i >= 0; i--) if (s.values[i] !== null) return i;
    return -1;
  });
  const endYs = visible.map((s, j) => (lastIdx[j] >= 0 ? y(s.values[lastIdx[j]]!) : NaN));
  const sorted = [...endYs].filter(Number.isFinite).sort((a, b) => a - b);
  const separated = sorted.every((v, i) => i === 0 || v - sorted[i - 1] >= 14);
  const wantEnd = spec.endLabels === true || (spec.endLabels === "auto" && visible.length >= 2 && visible.length <= 4);
  const showEnd = wantEnd && separated;
  const endW = showEnd ? Math.max(...visible.map((s) => measureText(s.name))) + 14 : 0;

  // value labels
  const labelMode = spec.valueLabels === "auto" ? (visible.length === 1 ? "last" : "none") : spec.valueLabels;
  const valueLabelPts: { j: number; i: number; below?: boolean }[] = [];
  if (labelMode !== "none") {
    visible.forEach((s, j) => {
      const present = s.values.map((v, i) => [v, i] as const).filter(([v]) => v !== null) as [number, number][];
      if (!present.length) return;
      if (labelMode === "last") valueLabelPts.push({ j, i: present[present.length - 1][1] });
      if (labelMode === "max" || labelMode === "min-max") valueLabelPts.push({ j, i: present.reduce((a, b) => (b[0] > a[0] ? b : a))[1] });
      if (labelMode === "min-max") valueLabelPts.push({ j, i: present.reduce((a, b) => (b[0] < a[0] ? b : a))[1], below: true });
    });
  }
  const lastLabelW = Math.max(0, ...valueLabelPts.filter((p) => p.i === n - 1).map((p) => measureText(valueFmt(visible[p.j].values[p.i]!), FONT, 600) / 2));

  const left = (spec.yAxis.show ? tickW + 10 : 4) + (spec.yAxis.label ? 20 : 0);
  const right = Math.max(12, endW, lastLabelW + 4);
  const plotW = width - left - right;
  const plot: Plot = { left, top, width: plotW, height: plotH };

  // ---- x scale ----
  const pad = spec.xType === "category" ? Math.min(24, plotW / (2 * Math.max(1, n))) : 0;
  const x0 = spec.xs[0];
  const x1 = spec.xs[n - 1] ?? x0;
  const x = n === 1 ? () => left + plotW / 2 : linear(x0, x1, left + pad, left + plotW - pad);
  const xPx = spec.xs.map((v) => x(v));

  const maxTicks = Math.max(2, Math.floor(plotW / 72));
  let xTicks: Tick[];
  if (spec.xType === "time") xTicks = timeTicks(x0, x1, maxTicks).map((t) => ({ pos: x(t.value), text: t.text }));
  else if (spec.xType === "number") {
    const nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
    xTicks = niceTicks(x0, x1, Math.min(maxTicks, 8), false)
      .filter((v) => v >= x0 && v <= x1)
      .map((v) => ({ pos: x(v), text: nf.format(v) }));
  } else xTicks = spec.xLabels.map((l, i) => ({ pos: xPx[i], text: l }));
  xTicks = thinTicks(xTicks, (t) => measureText(t));

  // ---- lines ----
  const fi = spec.forecastIndex;
  const lines = visible
    .map((s) => {
      const color = colorOf(spec, s, spec.series.indexOf(s));
      const dim = spec.highlight.length > 0 && !spec.highlight.includes(s.name);
      let solid = "";
      let dashed = "";
      const areas: string[] = [];
      const bands: string[] = [];
      for (const run of runs(s.values)) {
        const pts: Pt[] = run.map((i) => [xPx[i], y(s.values[i]!)]);
        const segs = segments(pts, spec.curve);
        // Split segments into actual (solid) vs projected (dashed).
        let cur: "s" | "d" | null = null;
        segs.forEach((seg, k) => {
          const style = fi >= 0 && run[k] >= fi ? "d" : "s";
          if (style !== cur) {
            const start = `M${pts[k][0]},${pts[k][1]}`;
            if (style === "s") solid += start;
            else dashed += start;
            cur = style;
          }
          if (style === "s") solid += seg;
          else dashed += seg;
        });
        if (pts.length === 1) solid += `M${pts[0][0]},${pts[0][1]}h0`; // lone point: a dot via round cap
        if (spec.area && pts.length > 1) {
          const base = y(Math.min(Math.max(0, d0), d1));
          areas.push(`M${pts[0][0]},${pts[0][1]}${segs.join("")}L${pts[pts.length - 1][0]},${base}L${pts[0][0]},${base}Z`);
        }
      }
      if (s.band) {
        const { lower, upper } = s.band;
        for (const run of runs(lower.map((l, i) => (l === null || upper[i] === null ? null : l)))) {
          if (run.length < 2) continue;
          const up: Pt[] = run.map((i) => [xPx[i], y(upper[i]!)]);
          const low: Pt[] = run.map((i): Pt => [xPx[i], y(lower[i]!)]).reverse();
          bands.push(`M${up[0][0]},${up[0][1]}${segments(up, spec.curve).join("")}L${low[0][0]},${low[0][1]}${segments(low, spec.curve).join("")}Z`);
        }
      }
      const markerIdx =
        spec.markers === "all" || (spec.markers === "auto" && n <= 12)
          ? s.values.map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0)
          : spec.markers === "none"
            ? []
            : [lastIdx[visible.indexOf(s)]].filter((i) => i >= 0);
      return {
        name: s.name,
        series: s,
        color,
        fill: SERIES_COLORS[color].fill,
        dim,
        solid,
        dashed,
        areas,
        bands,
        markers: markerIdx.map((i): Pt => [xPx[i], y(s.values[i]!)]),
      };
    })
    // Emphasised series draw last, on top.
    .sort((a, b) => Number(b.dim) - Number(a.dim));

  const valueLabels = valueLabelPts.map(({ j, i, below }) => {
    const v = visible[j].values[i]!;
    const px = xPx[i];
    return {
      x: px,
      y: below ? y(v) + 18 : y(v) - 10,
      text: valueFmt(v),
      anchor: (px > left + plotW - 30 && !showEnd ? "end" : px < left + 30 ? "start" : "middle") as "start" | "middle" | "end",
    };
  });

  const endLabels = showEnd
    ? visible.flatMap((s, j) => (lastIdx[j] >= 0 ? [{ x: xPx[lastIdx[j]] + 8, y: endYs[j], text: s.name }] : []))
    : [];

  const zeroY = d0 < 0 && d1 > 0 ? y(0) : d0 === 0 ? y(0) : null;

  return {
    height,
    plot,
    y,
    d0,
    d1,
    xPx,
    xTicks,
    yTicks: yTickValues.map((v, i) => ({ pos: y(v), text: yTexts[i] })),
    lines,
    valueLabels,
    endLabels,
    zeroY,
    forecastX: fi > 0 ? xPx[fi] : null,
  };
}

/** Consecutive runs of non-null indices — nulls break the line. */
function runs(values: (number | null)[]): number[][] {
  const out: number[][] = [];
  let cur: number[] = [];
  values.forEach((v, i) => {
    if (v === null) {
      if (cur.length) out.push(cur);
      cur = [];
    } else cur.push(i);
  });
  if (cur.length) out.push(cur);
  return out;
}

/** One path fragment per segment i → i+1 (no leading M). */
function segments(p: Pt[], curve: ResolvedLineChartSpec["curve"]): string[] {
  const n = p.length;
  if (n < 2) return [];
  const r = (v: number) => Math.round(v * 100) / 100;
  if (curve === "linear") return p.slice(1).map(([x, y]) => `L${r(x)},${r(y)}`);
  if (curve === "step") return p.slice(1).map(([x, y]) => `H${r(x)}V${r(y)}`);

  // Monotone cubic (Fritsch–Carlson): smooth, never overshoots the data.
  const d = p.slice(1).map((q, i) => (q[1] - p[i][1]) / (q[0] - p[i][0] || 1));
  const m = p.map((_, i) => (i === 0 ? d[0] : i === n - 1 ? d[n - 2] : d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2));
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / d[i];
    const b = m[i + 1] / d[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * d[i];
      m[i + 1] = t * b * d[i];
    }
  }
  return p.slice(1).map((q, i) => {
    const dx = (q[0] - p[i][0]) / 3;
    return `C${r(p[i][0] + dx)},${r(p[i][1] + m[i] * dx)} ${r(q[0] - dx)},${r(q[1] - m[i + 1] * dx)} ${r(q[0])},${r(q[1])}`;
  });
}
