import { useChartWarnings, useHiddenSeries } from "../shared/hooks";
import { anchorAbove } from "../shared/layout";
import type { Plot } from "../shared/layout";
import { FONT, HALO, thinTicks } from "../shared/layout";
import { useMemo, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { CartesianAxes, ReferenceRule } from "../shared/axes";
import { ChartFrame } from "../shared/chart-frame";
import { CHART_TOKENS, SERIES_COLORS } from "../shared/palette";
import { linear, makeFormatter, measureText, niceTicks } from "../shared/scale";
import { ChartTooltip } from "../shared/tooltip";
import { normalizeScatterSpec } from "./spec";
import type { ResolvedPoint, ResolvedScatterSpec, ScatterPlotSpec } from "./spec";

export interface ScatterPlotProps {
  spec: ScatterPlotSpec | unknown;
  className?: string;
  loading?: boolean;
  onWarnings?: (warnings: string[]) => void;
  onPointClick?: (point: { x: number; y: number; label?: string; size?: number; series: string }) => void;
}

const HIT_RADIUS = 24; // px: the pointer only has to be closest, not dead-centre

export function ScatterPlot({ spec: input, className = "", loading = false, onWarnings, onPointClick }: ScatterPlotProps) {
  const { spec, warnings } = useMemo(() => normalizeScatterSpec(input), [input]);
  useChartWarnings("ScatterPlot", warnings, onWarnings);
  const [hidden, toggle] = useHiddenSeries(spec.series.length);
  const [active, setActive] = useState<number | null>(null);

  const points = useMemo(() => spec.points.filter((p) => !hidden.has(spec.series[p.series].name)), [spec, hidden]);
  const fx = useMemo(() => makeFormatter(spec.xAxis.format, Math.max(0, ...spec.points.map((p) => Math.abs(p.x)))), [spec]);
  const fy = useMemo(() => makeFormatter(spec.yAxis.format, Math.max(0, ...spec.points.map((p) => Math.abs(p.y)))), [spec]);
  const nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
  const multi = spec.series.length > 1;
  const xName = spec.xAxis.label ?? "X";
  const yName = spec.yAxis.label ?? "Y";

  return (
    <ChartFrame
      title={spec.title}
      subtitle={spec.subtitle}
      className={className}
      loading={loading}
      empty={spec.points.length === 0}
      emptyMessage={spec.emptyMessage}
      emptyHeight={spec.height}
      legend={multi ? { shape: "dot", items: spec.series.map((s) => ({ name: s.name, color: s.color, off: hidden.has(s.name) })), onToggle: toggle } : null}
      table={{
        columns: ["Point", ...(multi ? ["Group"] : []), xName, yName, ...(spec.hasSize ? [spec.sizeLabel ?? "Size"] : [])],
        rows: points.map((p, i) => [
          p.label ?? `#${i + 1}`,
          ...(multi ? [spec.series[p.series].name] : []),
          fx(p.x),
          fy(p.y),
          ...(spec.hasSize ? [p.size === undefined ? "—" : nf.format(p.size)] : []),
        ]),
        numeric: multi ? [2, 3, 4] : [1, 2, 3],
      }}
    >
      {(width) => {
        const g = layout(spec, points, width, fx, fy);
        const pick = (e: PointerEvent<SVGRectElement>) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const mx = e.clientX - rect.left + g.plot.left;
          const my = e.clientY - rect.top + g.plot.top;
          let best = -1;
          let bestD = HIT_RADIUS ** 2;
          g.dots.forEach((d, i) => {
            const dd = (d.cx - mx) ** 2 + (d.cy - my) ** 2 - d.r ** 2;
            if (dd < bestD) {
              bestD = dd;
              best = i;
            }
          });
          setActive(best >= 0 ? best : null);
        };
        // Keyboard: walk points left → right.
        const order = g.dots.map((_, i) => i).sort((a, b) => g.dots[a].cx - g.dots[b].cx);
        const key = (e: KeyboardEvent<SVGRectElement>) => {
          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
            e.preventDefault();
            const pos = active === null ? -1 : order.indexOf(active);
            const next = e.key === "ArrowRight" ? (pos + 1) % order.length : (pos - 1 + order.length) % order.length;
            setActive(order[next]);
          } else if (e.key === "Escape") setActive(null);
          else if ((e.key === "Enter" || e.key === " ") && active !== null) {
            e.preventDefault();
            fire(active);
          }
        };
        const fire = (i: number) => {
          const p = points[i];
          onPointClick?.({ x: p.x, y: p.y, label: p.label, size: p.size, series: spec.series[p.series].name });
        };
        const ap = active !== null ? points[active] : null;
        const ad = active !== null ? g.dots[active] : null;

        return (
          <>
            <svg width={width} height={g.height} className="block overflow-visible select-none" style={{ fontSize: FONT }} role="group" aria-label={`${spec.title ?? "Scatter plot"}. ${points.length} points. Use left and right arrow keys to read points.`}>
              <CartesianAxes
                plot={g.plot}
                height={g.height}
                xTicks={spec.xAxis.show ? g.xTicks : []}
                yTicks={spec.yAxis.show ? g.yTicks : []}
                xGrid={spec.xAxis.gridlines}
                yGrid={spec.yAxis.gridlines}
                xTitle={spec.xAxis.label}
                yTitle={spec.yAxis.label}
              />
              {g.refs.map((r, i) => (
                <ReferenceRule key={i} {...r} plot={g.plot} />
              ))}
              {g.trends.map((t, i) => (
                <g key={i} pointerEvents="none">
                  <line {...t.line} stroke={SERIES_COLORS[t.color].fill} strokeWidth={2} strokeDasharray="6 4" strokeLinecap="round" opacity={0.85} />
                  <text x={t.line.x2} y={t.line.y2 < t.line.y1 ? t.line.y2 + 18 : t.line.y2 - 8} textAnchor="end" fill={CHART_TOKENS.textMuted} fontSize={11} {...HALO}>
                    {t.label}
                  </text>
                </g>
              ))}
              {/* Biggest first so small dots stay on top; each carries a 2px surface ring */}
              {g.drawOrder.map((i) => {
                const d = g.dots[i];
                return (
                  <circle
                    key={i}
                    cx={d.cx}
                    cy={d.cy}
                    r={active === i ? d.r + 2 : d.r}
                    fill={SERIES_COLORS[spec.series[points[i].series].color].fill}
                    fillOpacity={d.dim ? 0.45 : spec.hasSize ? 0.75 : 1}
                    stroke="var(--color-surface)"
                    strokeWidth={2}
                    className="motion-safe:transition-[r,cx,cy] motion-safe:duration-200"
                  />
                );
              })}
              {g.labels.map((l, i) => (
                <text key={i} x={l.x} y={l.y} textAnchor={l.anchor} fill={CHART_TOKENS.textSecondary} fontSize={11} {...HALO} pointerEvents="none">
                  {l.text}
                </text>
              ))}
              <rect
                x={g.plot.left}
                y={g.plot.top}
                width={g.plot.width}
                height={g.plot.height}
                fill="transparent"
                tabIndex={0}
                aria-label={ap ? `${ap.label ?? "Point"}: ${xName} ${fx(ap.x)}, ${yName} ${fy(ap.y)}` : "Points"}
                className={["outline-none", ap && onPointClick ? "cursor-pointer" : ""].join(" ")}
                onPointerMove={pick}
                onPointerLeave={() => setActive(null)}
                onBlur={() => setActive(null)}
                onKeyDown={key}
                onClick={() => active !== null && fire(active)}
              />
            </svg>
            {ap && ad && (
              <ChartTooltip
                {...anchorAbove(ad.cx, ad.cy - ad.r, width)}
                title={[ap.label, multi ? spec.series[ap.series].name : undefined].filter(Boolean).join(" · ") || undefined}
                rows={[
                  { color: spec.series[ap.series].color, value: fx(ap.x), label: xName },
                  { value: fy(ap.y), label: yName },
                  ...(ap.size !== undefined ? [{ value: nf.format(ap.size), label: spec.sizeLabel ?? "Size" }] : []),
                ]}
              />
            )}
          </>
        );
      }}
    </ChartFrame>
  );
}

export default ScatterPlot;

function layout(spec: ResolvedScatterSpec, points: ResolvedPoint[], width: number, fx: (v: number) => string, fy: (v: number) => string) {
  const ext = (vals: number[], extra: (number | undefined)[]) => {
    const all = [...vals, ...extra.filter((v): v is number => v !== undefined)];
    if (!all.length) return [0, 1];
    // Pad so no dot sits on an axis line.
    const lo = Math.min(...all);
    const hi = Math.max(...all);
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.05;
    return [lo >= 0 ? Math.max(0, lo - pad) : lo - pad, hi <= 0 ? Math.min(0, hi + pad) : hi + pad];
  };
  const [xlo, xhi] = ext(points.map((p) => p.x), [spec.xAxis.min, spec.xAxis.max, ...spec.referenceLines.x.map((r) => r.value)]);
  const [ylo, yhi] = ext(points.map((p) => p.y), [spec.yAxis.min, spec.yAxis.max, ...spec.referenceLines.y.map((r) => r.value)]);
  const xTickValues = niceTicks(xlo, xhi, spec.xAxis.tickCount + 1, spec.xAxis.includeZero);
  const yTickValues = niceTicks(ylo, yhi, spec.yAxis.tickCount, spec.yAxis.includeZero);
  const axFx = makeFormatter(spec.xAxis.format, Math.max(...xTickValues.map(Math.abs)));
  const axFy = makeFormatter(spec.yAxis.format, Math.max(...yTickValues.map(Math.abs)));
  const yTexts = yTickValues.map(axFy);
  const tickW = Math.max(...yTexts.map((t) => measureText(t)));

  const top = spec.referenceLines.x.some((r) => r.label) ? 22 : 14;
  const bottom = (spec.xAxis.show ? 28 : 8) + (spec.xAxis.label ? 18 : 0);
  const left = (spec.yAxis.show ? tickW + 10 : 4) + (spec.yAxis.label ? 20 : 0);
  const right = 16;
  const plot: Plot = { left, top, width: width - left - right, height: spec.height - top - bottom };
  const x = linear(xTickValues[0], xTickValues[xTickValues.length - 1], plot.left, plot.left + plot.width);
  const y = linear(yTickValues[0], yTickValues[yTickValues.length - 1], plot.top + plot.height, plot.top);

  // Bubble sizes: area ∝ value (sqrt scale), 3–16px radius.
  const maxSize = Math.max(0, ...points.map((p) => p.size ?? 0));
  const radius = (s?: number) => (s === undefined || !maxSize ? 4.5 : 3 + Math.sqrt(s / maxSize) * 13);

  const hl = new Set(spec.highlight);
  const dots = points.map((p) => ({ cx: x(p.x), cy: y(p.y), r: radius(p.size), dim: hl.size > 0 && !(p.label && hl.has(p.label)) }));
  const drawOrder = dots.map((_, i) => i).sort((a, b) => Number(dots[b].dim) - Number(dots[a].dim) || dots[b].r - dots[a].r);

  // Point labels: selective by default.
  const mode = spec.labels === "auto" ? (hl.size ? "highlighted" : points.length <= 12 && points.some((p) => p.label) ? "all" : "none") : spec.labels;
  const labels: { x: number; y: number; text: string; anchor: "start" | "end" }[] = [];
  const placed: { x0: number; x1: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (!p.label || mode === "none" || (mode === "highlighted" && !hl.has(p.label))) return;
    const d = dots[i];
    const w = measureText(p.label, 11);
    const right = d.cx + d.r + 4 + w < plot.left + plot.width;
    const lx = right ? d.cx + d.r + 4 : d.cx - d.r - 4;
    const box = { x0: right ? lx : lx - w, x1: right ? lx + w : lx, y: d.cy };
    // Skip a label that would overlap one already placed — the tooltip still has it.
    if (placed.some((b) => Math.abs(b.y - box.y) < 12 && b.x0 < box.x1 && box.x0 < b.x1)) return;
    placed.push(box);
    labels.push({ x: lx, y: d.cy + 4, text: p.label, anchor: right ? "start" : "end" });
  });

  // Trend lines (least squares) across the visible x range of their points.
  const trends: { line: { x1: number; y1: number; x2: number; y2: number }; color: ResolvedScatterSpec["series"][number]["color"]; label: string }[] = [];
  const fit = (pts: ResolvedPoint[], color: ResolvedScatterSpec["series"][number]["color"]) => {
    if (pts.length < 3) return;
    const n = pts.length;
    const mx = pts.reduce((a, p) => a + p.x, 0) / n;
    const my = pts.reduce((a, p) => a + p.y, 0) / n;
    let sxy = 0;
    let sxx = 0;
    let syy = 0;
    for (const p of pts) {
      sxy += (p.x - mx) * (p.y - my);
      sxx += (p.x - mx) ** 2;
      syy += (p.y - my) ** 2;
    }
    if (!sxx) return;
    const slope = sxy / sxx;
    const r2 = syy ? (sxy * sxy) / (sxx * syy) : 1;
    const a = Math.min(...pts.map((p) => p.x));
    const b = Math.max(...pts.map((p) => p.x));
    const at = (v: number) => my + slope * (v - mx);
    trends.push({ line: { x1: x(a), y1: y(at(a)), x2: x(b), y2: y(at(b)) }, color, label: `r² ${r2.toFixed(2)}` });
  };
  if (spec.trendline === "all") fit(points, spec.series.length === 1 ? spec.series[0].color : "neutral");
  if (spec.trendline === "per-series") spec.series.forEach((s, si) => fit(points.filter((p) => p.series === si), s.color));

  const refs = [
    ...spec.referenceLines.x.map((r) => ({ orientation: "vertical" as const, pos: x(r.value), label: r.label ? `${r.label} · ${fx(r.value)}` : undefined })),
    ...spec.referenceLines.y.map((r) => ({ orientation: "horizontal" as const, pos: y(r.value), label: r.label ? `${r.label} · ${fy(r.value)}` : undefined })),
  ];

  return {
    height: spec.height,
    plot,
    dots,
    drawOrder,
    labels,
    trends,
    refs,
    xTicks: thinTicks(
      xTickValues.map((v) => ({ pos: x(v), text: axFx(v) })),
      (t) => measureText(t),
    ),
    yTicks: yTickValues.map((v, i) => ({ pos: y(v), text: yTexts[i] })),
  };
}
