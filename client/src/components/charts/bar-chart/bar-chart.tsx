import { useChartWarnings, useHiddenSeries } from "../shared/hooks";
import { HALO, FONT, thinTicks } from "../shared/layout";
import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { normalizeBarChartSpec } from "./normalize";
import { ChartFrame } from "../shared/chart-frame";
import { CHART_TOKENS, SERIES_COLORS, inkOn } from "../shared/palette";
import { makeFormatter, measureText, niceTicks, truncateToWidth } from "../shared/scale";
import { ChartTooltip } from "../shared/tooltip";
import type { BarChartSpec, ResolvedBarChartSpec, ValueLabels } from "./types";

export interface BarChartClickEvent {
  category: string;
  /** Raw (un-normalised) value of every visible series at that category. */
  values: { series: string; value: number | null }[];
}

export interface BarChartProps {
  /** The spec, usually straight from the AI backend. Untrusted input is fine — it is normalised. */
  spec: BarChartSpec | unknown;
  className?: string;
  /** Keep the previous render at reduced opacity while new data loads. */
  loading?: boolean;
  /** Receives every coercion the normaliser made, e.g. to send back to the model. */
  onWarnings?: (warnings: string[]) => void;
  onCategoryClick?: (event: BarChartClickEvent) => void;
}

// Mark specs
const BAR_MAX = 24; // px, bars never fill their slot
const GAP = 2; // px surface gap between touching marks
const RADIUS = 4; // px rounded data-end

interface Row {
  category: string;
  raw: (number | null)[]; // per visible series
  display: (number | null)[]; // percent-converted when layout = percent
  pos: number; // stacked positive total (display units)
  neg: number; // stacked negative total
  total: number; // raw total
}

interface Bar {
  key: string;
  row: number;
  series: number;
  path: string;
  fill: string;
  inside?: { x: number; y: number; text: string; color: string };
}

interface Label {
  key: string;
  x: number;
  y: number;
  text: string;
  anchor: "start" | "middle" | "end";
}

export function BarChart({ spec: input, className = "", loading = false, onWarnings, onCategoryClick }: BarChartProps) {
  const { spec, warnings } = useMemo(() => normalizeBarChartSpec(input), [input]);
  useChartWarnings("BarChart", warnings, onWarnings);

  const [hidden, toggleSeries] = useHiddenSeries(spec.series.length);
  const [active, setActive] = useState<number | null>(null);
  const hitRefs = useRef<(SVGRectElement | null)[]>([]);

  const visible = useMemo(() => spec.series.filter((s) => !hidden.has(s.name)), [spec, hidden]);
  const rows = useMemo(() => buildRows(spec, visible), [spec, visible]);
  const isEmpty = rows.length === 0 || rows.every((r) => r.raw.every((v) => v === null));

  const onKeyDown = (e: KeyboardEvent<SVGSVGElement>) => {
    if (active === null) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    hitRefs.current[(active + step + rows.length) % rows.length]?.focus();
  };

  const tooltipFmt = useMemo(() => {
    const maxAbs = Math.max(0, ...spec.series.flatMap((s) => s.values.map((v) => Math.abs(v ?? 0))));
    return makeFormatter(spec.valueFormat, maxAbs);
  }, [spec]);

  const fireClick = (i: number) =>
    onCategoryClick?.({
      category: rows[i].category,
      values: visible.map((s, j) => ({ series: s.name, value: rows[i].raw[j] })),
    });

  const stackedTotal = spec.layout !== "grouped" && visible.length > 1;
  const fmtCell = (v: number | null) => (v === null ? "—" : tooltipFmt(v));

  return (
    <ChartFrame
      title={spec.title}
      subtitle={spec.subtitle}
      className={className}
      loading={loading}
      empty={isEmpty}
      emptyMessage={spec.emptyMessage}
      emptyHeight={spec.orientation === "vertical" ? spec.height : 160}
      legend={
        spec.legend.show
          ? { items: spec.series.map((s) => ({ name: s.name, color: s.color, off: hidden.has(s.name) })), onToggle: toggleSeries }
          : null
      }
      table={{
        columns: [spec.categoryAxis.label ?? "Category", ...visible.map((s) => s.name), ...(stackedTotal ? ["Total"] : [])],
        rows: rows.map((r) => [r.category, ...r.raw.map(fmtCell), ...(stackedTotal ? [tooltipFmt(r.total)] : [])]),
        numeric: visible.map((_, i) => i + 1).concat(stackedTotal ? [visible.length + 1] : []),
      }}
    >
      {(width) => {
        const geo = layoutChart(spec, visible, rows, width);
        return (
          <>
            <svg
              width={width}
              height={geo.height}
              role="group"
              aria-label={describe(spec, visible.map((s) => s.name))}
              onKeyDown={onKeyDown}
              className="block overflow-visible select-none"
              style={{ fontFamily: "inherit", fontSize: FONT }}
            >
          {/* Gridlines + value ticks */}
          {spec.valueAxis.gridlines &&
            geo.ticks.map((t) => <line key={`g${t.value}`} {...t.grid} stroke={CHART_TOKENS.grid} strokeWidth={1} shapeRendering="crispEdges" />)}
          {spec.valueAxis.show &&
            geo.ticks.map((t) => (
              <text key={`t${t.value}`} {...t.label} fill={CHART_TOKENS.textMuted} style={{ fontVariantNumeric: "tabular-nums" }}>
                {t.text}
              </text>
            ))}

          {/* Hover wash behind the active category */}
          {active !== null && geo.bands[active] && <rect {...geo.bands[active]} rx={6} fill={CHART_TOKENS.hoverWash} opacity={0.7} />}

          {/* Bars */}
          {geo.bars.map((b) => {
            const dimmed = spec.highlight.length > 0 && !spec.highlight.includes(rows[b.row].category);
            return (
              <path
                key={b.key}
                d={b.path}
                fill={b.fill}
                opacity={dimmed ? 0.35 : 1}
                className="motion-safe:transition-[d,opacity,filter] motion-safe:duration-300"
                style={{ filter: active === b.row ? "brightness(1.15)" : undefined }}
              />
            );
          })}

          {/* Zero baseline — bars grow from here */}
          <line {...geo.baseline} stroke={CHART_TOKENS.baseline} strokeWidth={1} shapeRendering="crispEdges" />

          {/* Reference lines (targets, budgets) */}
          {geo.references.map((r, i) => (
            <g key={`r${i}`}>
              <line {...r.line} stroke={CHART_TOKENS.reference} strokeWidth={1} strokeDasharray="4 3" shapeRendering="crispEdges" />
              {r.label && (
                <text {...r.label} fill={CHART_TOKENS.textSecondary} fontSize={11} {...HALO}>
                  {r.label.text}
                </text>
              )}
            </g>
          ))}

          {/* Labels printed inside stacked segments (only where they fit) */}
          {geo.bars.map(
            (b) =>
              b.inside && (
                <text key={`in${b.key}`} x={b.inside.x} y={b.inside.y} fill={b.inside.color} fontSize={11} fontWeight={600} textAnchor="middle" pointerEvents="none">
                  {b.inside.text}
                </text>
              ),
          )}

          {/* Value labels at bar tips */}
          {geo.valueLabels.map((l) => (
            <text key={l.key} x={l.x} y={l.y} textAnchor={l.anchor} fill={CHART_TOKENS.textPrimary} fontWeight={600} pointerEvents="none" {...HALO}>
              {l.text}
            </text>
          ))}

          {/* Category labels */}
          {spec.categoryAxis.show &&
            geo.categoryLabels.map((l) => (
              <text key={l.key} x={l.x} y={l.y} textAnchor={l.anchor} fill={CHART_TOKENS.textSecondary}>
                <title>{rows[Number(l.key)].category}</title>
                {l.text}
              </text>
            ))}

          {/* Axis titles */}
          {geo.axisTitles.map((a) => (
            <text key={a.key} x={a.x} y={a.y} transform={a.rotate ? `rotate(-90 ${a.x} ${a.y})` : undefined} textAnchor="middle" fill={CHART_TOKENS.textMuted} fontSize={11}>
              {a.text}
            </text>
          ))}

          {/* Hit targets: the whole category band, larger than any bar */}
          {geo.bands.map((band, i) => (
            <rect
              key={`hit${i}`}
              ref={(el) => {
                hitRefs.current[i] = el;
              }}
              {...band}
              fill="transparent"
              tabIndex={0}
              role={onCategoryClick ? "button" : "img"}
              aria-label={`${rows[i].category}: ${visible
                .map((s, j) => `${s.name} ${rows[i].raw[j] === null ? "no data" : tooltipFmt(rows[i].raw[j]!)}`)
                .join(", ")}`}
              className={["outline-none", onCategoryClick ? "cursor-pointer" : ""].join(" ")}
              onPointerEnter={() => setActive(i)}
              onPointerLeave={() => setActive((a) => (a === i ? null : a))}
              onFocus={() => setActive(i)}
              onBlur={() => setActive((a) => (a === i ? null : a))}
              onClick={() => fireClick(i)}
              onKeyDown={(e) => {
                if (e.key === "Escape") e.currentTarget.blur();
                if (onCategoryClick && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  fireClick(i);
                }
              }}
            />
          ))}
            </svg>

            {active !== null && rows[active] && geo.tooltips[active] && (
              <ChartTooltip
                {...geo.tooltips[active]}
                title={rows[active].category}
                rows={visible.map((s, j) => {
                  const share = spec.layout === "percent" ? rows[active].display[j] : null;
                  return {
                    color: s.color,
                    value: fmtCell(rows[active].raw[j]),
                    extra: share !== null ? `(${Math.round(share)}%)` : undefined,
                    label: s.name,
                  };
                })}
                footer={stackedTotal ? { value: tooltipFmt(rows[active].total), label: "Total" } : undefined}
              />
            )}
          </>
        );
      }}
    </ChartFrame>
  );
}

export default BarChart;

// ---------------------------------------------------------------------------
// Data + layout (pure functions)
// ---------------------------------------------------------------------------

function buildRows(spec: ResolvedBarChartSpec, visible: ResolvedBarChartSpec["series"]): Row[] {
  const percent = spec.layout === "percent";
  const rows = spec.categories.map((category, ci) => {
    const raw = visible.map((s) => s.values[ci]);
    const absTotal = raw.reduce<number>((a, v) => a + Math.abs(v ?? 0), 0);
    const display = percent ? raw.map((v) => (v === null ? null : absTotal ? (Math.abs(v) / absTotal) * 100 : 0)) : raw;
    let pos = 0;
    let neg = 0;
    for (const v of display) {
      if (v === null) continue;
      if (v > 0) pos += v;
      else neg += v;
    }
    const total = raw.reduce<number>((a, v) => a + (v ?? 0), 0);
    return { category, raw, display, pos, neg, total };
  });
  if (spec.sort !== "none") {
    const dir = spec.sort === "asc" ? 1 : -1;
    rows.sort((a, b) => dir * (a.total - b.total));
  }
  return rows;
}

function resolveLabelMode(spec: ResolvedBarChartSpec, seriesCount: number): ValueLabels {
  const stacked = spec.layout !== "grouped";
  let mode = spec.valueLabels;
  if (mode === "auto") mode = stacked ? (seriesCount > 1 ? "totals" : "max") : seriesCount === 1 ? "max" : "none";
  if (mode === "totals" && !stacked) mode = "none";
  if (spec.layout === "percent" && mode !== "all") mode = "none"; // every total is 100%
  return mode;
}

function layoutChart(spec: ResolvedBarChartSpec, visible: ResolvedBarChartSpec["series"], rows: Row[], width: number) {
  const isV = spec.orientation === "vertical";
  const stacked = spec.layout !== "grouped";
  const percent = spec.layout === "percent";
  const n = rows.length;
  const k = stacked ? 1 : Math.max(1, visible.length);

  // ---- value domain ----
  let dMin = 0;
  let dMax = 0;
  for (const r of rows) {
    if (stacked) {
      dMin = Math.min(dMin, r.neg);
      dMax = Math.max(dMax, r.pos);
    } else {
      for (const v of r.display) {
        if (v === null) continue;
        dMin = Math.min(dMin, v);
        dMax = Math.max(dMax, v);
      }
    }
  }
  if (!percent) {
    for (const ref of spec.referenceLines) {
      dMin = Math.min(dMin, ref.value);
      dMax = Math.max(dMax, ref.value);
    }
    if (spec.valueAxis.min !== undefined) dMin = Math.min(dMin, spec.valueAxis.min);
    if (spec.valueAxis.max !== undefined) dMax = Math.max(dMax, spec.valueAxis.max);
  }
  const tickValues = percent ? [0, 25, 50, 75, 100] : niceTicks(dMin, dMax, spec.valueAxis.tickCount);
  const d0 = tickValues[0];
  const d1 = tickValues[tickValues.length - 1];
  const axisFmt = makeFormatter(spec.valueFormat, Math.max(Math.abs(d0), Math.abs(d1)), percent);
  const valueFmt = makeFormatter(spec.valueFormat, Math.max(Math.abs(dMin), Math.abs(dMax)));
  const tickTexts = tickValues.map(axisFmt);
  const tickW = Math.max(...tickTexts.map((t) => measureText(t, FONT)));

  // ---- value labels (decide before margins so they get room) ----
  const labelMode = resolveLabelMode(spec, visible.length);
  type Pending = { row: number; series: number | null; value: number; at: number };
  const pending: Pending[] = [];
  if (labelMode !== "none") {
    if (stacked) {
      const pick = (i: number) => pending.push({ row: i, series: null, value: rows[i].total, at: rows[i].pos > 0 || rows[i].neg === 0 ? rows[i].pos : rows[i].neg });
      const totals = rows.map((r) => r.total);
      if (labelMode === "totals" || labelMode === "all") rows.forEach((_, i) => pick(i));
      if (labelMode === "max" || labelMode === "min-max") pick(totals.indexOf(Math.max(...totals)));
      if (labelMode === "min-max") {
        const mi = totals.indexOf(Math.min(...totals));
        if (!pending.some((p) => p.row === mi)) pick(mi);
      }
      if (labelMode === "last") pick(n - 1);
      if (percent) pending.length = 0;
    } else {
      const present: Pending[] = [];
      rows.forEach((r, i) =>
        r.display.forEach((v, j) => {
          if (v !== null) present.push({ row: i, series: j, value: v, at: v });
        }),
      );
      if (labelMode === "all") pending.push(...present);
      if (labelMode === "last") pending.push(...present.filter((p) => p.row === n - 1));
      if ((labelMode === "max" || labelMode === "min-max") && present.length) {
        pending.push(present.reduce((a, b) => (b.value > a.value ? b : a)));
        if (labelMode === "min-max") {
          const lo = present.reduce((a, b) => (b.value < a.value ? b : a));
          if (lo !== pending[0]) pending.push(lo);
        }
      }
    }
  }
  const labelTexts = pending.map((p) => valueFmt(p.value));
  const labelW = Math.max(0, ...labelTexts.map((t) => measureText(t, FONT, 600)));
  const negLabelRoom = pending.some((p) => p.at < 0) ? (isV ? 16 : labelW + 8) : 0;

  // ---- margins ----
  const catLabelW = Math.max(0, ...rows.map((r) => measureText(r.category, FONT)));
  let mL: number, mR: number, mT: number, mB: number, height: number;
  let band: number;
  if (isV) {
    mL = (spec.valueAxis.show ? tickW + 10 : 4) + (spec.valueAxis.label ? 20 : 0);
    mR = 8;
    mT = pending.length || spec.referenceLines.length ? 22 : 10;
    mB = (spec.categoryAxis.show ? 26 : 6) + (spec.categoryAxis.label ? 20 : 0) + negLabelRoom;
    height = spec.height;
    band = (width - mL - mR) / n;
  } else {
    const catRoom = spec.categoryAxis.show ? Math.min(catLabelW, width * 0.3) + 12 : 4;
    mL = catRoom + (spec.categoryAxis.label ? 20 : 0) + negLabelRoom;
    mR = Math.max(tickW / 2 + 4, pending.length ? labelW + 10 : 8);
    mT = spec.referenceLines.some((r) => r.label) ? 20 : 6;
    mB = (spec.valueAxis.show ? 24 : 6) + (spec.valueAxis.label ? 20 : 0);
    band = Math.max(32, k * 16 + (k - 1) * GAP + 16);
    height = mT + mB + band * n;
  }
  const plotW = width - mL - mR;
  const plotH = height - mT - mB;
  const valueLen = isV ? plotH : plotW;
  const toPx = (v: number) => (isV ? mT + valueLen * (1 - (v - d0) / (d1 - d0)) : mL + (valueLen * (v - d0)) / (d1 - d0));
  const catStart = (i: number) => (isV ? mL : mT) + i * band;
  const zero = toPx(0);

  const thickness = Math.max(1, Math.min(BAR_MAX, (band * 0.72 - GAP * (k - 1)) / k));

  // ---- bars ----
  const bars: Bar[] = [];
  const tips: { min: number; max: number }[] = rows.map(() => ({ min: zero, max: zero }));
  const recordTip = (i: number, px: number) => {
    tips[i].min = Math.min(tips[i].min, px);
    tips[i].max = Math.max(tips[i].max, px);
  };
  rows.forEach((r, i) => {
    if (stacked) {
      const c0 = catStart(i) + (band - thickness) / 2;
      let posAcc = 0;
      let negAcc = 0;
      const lastPos = r.display.reduce<number>((acc, v, j) => (v !== null && v > 0 ? j : acc), -1);
      const lastNeg = r.display.reduce<number>((acc, v, j) => (v !== null && v < 0 ? j : acc), -1);
      r.display.forEach((v, j) => {
        if (v === null || v === 0) return;
        const from = v > 0 ? posAcc : negAcc;
        const to = from + v;
        const hasPrev = v > 0 ? posAcc !== 0 : negAcc !== 0;
        if (v > 0) posAcc = to;
        else negAcc = to;
        let a = toPx(from);
        const b = toPx(to);
        const dir = Math.sign(b - a);
        if (hasPrev) a += dir * GAP;
        if (Math.abs(b - a) < 0.5) return;
        recordTip(i, b);
        const color = SERIES_COLORS[visible[j].color];
        const isEnd = j === (v > 0 ? lastPos : lastNeg);
        const bar: Bar = {
          key: `${i}-${j}`,
          row: i,
          series: j,
          path: barPath(isV, c0, c0 + thickness, a, b, isEnd ? RADIUS : 0),
          fill: color.fill,
        };
        // Inside label: only when the text fits with padding, never clipped.
        if (labelMode === "all") {
          const text = percent ? `${Math.round(v)}%` : valueFmt(r.raw[j] ?? 0);
          const segLen = Math.abs(b - a);
          const tw = measureText(text, 11, 600);
          const fits = isV ? segLen >= 18 && thickness >= tw + 8 : segLen >= tw + 12 && thickness >= 16;
          if (fits) {
            const mid = (a + b) / 2;
            const cm = c0 + thickness / 2;
            bar.inside = { x: isV ? cm : mid, y: isV ? mid + 4 : cm + 4, text, color: inkOn(color.hex) };
          }
        }
        bars.push(bar);
      });
    } else {
      const groupW = k * thickness + (k - 1) * GAP;
      r.display.forEach((v, j) => {
        if (v === null) return;
        const c0 = catStart(i) + (band - groupW) / 2 + j * (thickness + GAP);
        const b = toPx(v);
        recordTip(i, b);
        bars.push({
          key: `${i}-${j}`,
          row: i,
          series: j,
          path: barPath(isV, c0, c0 + thickness, zero, b, RADIUS),
          fill: SERIES_COLORS[visible[j].color].fill,
        });
      });
    }
  });

  // ---- value labels at tips ----
  const groupW = k * thickness + (k - 1) * GAP;
  const valueLabels: Label[] = [];
  pending.forEach((p, idx) => {
    const text = labelTexts[idx];
    const tip = toPx(p.at);
    const center =
      p.series === null ? catStart(p.row) + band / 2 : catStart(p.row) + (band - groupW) / 2 + p.series * (thickness + GAP) + thickness / 2;
    const negative = p.at < 0;
    if (isV) {
      // Skip labels that would collide with a neighbouring bar's label.
      if (p.series !== null && k > 1 && labelMode === "all" && measureText(text, FONT, 600) > thickness + GAP + 4) return;
      valueLabels.push({ key: `v${idx}`, x: center, y: negative ? tip + 14 : tip - 6, text, anchor: "middle" });
    } else {
      valueLabels.push({ key: `v${idx}`, x: negative ? tip - 6 : tip + 6, y: center + 4, text, anchor: negative ? "end" : "start" });
    }
  });

  // ---- ticks ----
  // Horizontal value labels sit side by side: drop every other one when they'd touch.
  const labelled = new Set(
    isV ? tickValues.map((_, i) => i) : thinTicks(tickValues.map((v, i) => ({ pos: toPx(v), text: tickTexts[i], i })), (t) => measureText(t, FONT), 12).map((t) => t.i),
  );
  const ticks = tickValues.map((v, i) => {
    const p = toPx(v);
    return {
      value: v,
      text: labelled.has(i) ? tickTexts[i] : "",
      grid: isV ? { x1: mL, x2: mL + plotW, y1: p, y2: p } : { x1: p, x2: p, y1: mT, y2: mT + plotH },
      label: isV
        ? { x: mL - 10, y: p + 4, textAnchor: "end" as const }
        : { x: p, y: mT + plotH + 17, textAnchor: "middle" as const },
    };
  });

  const baseline = isV ? { x1: mL, x2: mL + plotW, y1: zero, y2: zero } : { x1: zero, x2: zero, y1: mT, y2: mT + plotH };

  // ---- category labels (thinned + truncated so they never collide) ----
  const categoryLabels: Label[] = [];
  if (isV) {
    const stepEvery = Math.max(1, Math.ceil((Math.min(catLabelW, 120) + 8) / band));
    rows.forEach((r, i) => {
      if (i % stepEvery !== 0) return;
      const text = truncateToWidth(r.category, band * stepEvery - 8);
      if (text) categoryLabels.push({ key: String(i), x: catStart(i) + band / 2, y: mT + plotH + negLabelRoom + 18, text, anchor: "middle" });
    });
  } else {
    const room = Math.min(catLabelW, width * 0.3);
    rows.forEach((r, i) => {
      categoryLabels.push({ key: String(i), x: mL - 12 - negLabelRoom, y: catStart(i) + band / 2 + 4, text: truncateToWidth(r.category, room), anchor: "end" });
    });
  }

  // ---- axis titles ----
  const axisTitles: { key: string; x: number; y: number; text: string; rotate: boolean }[] = [];
  const sideTitle = isV ? spec.valueAxis.label : spec.categoryAxis.label;
  const bottomTitle = isV ? spec.categoryAxis.label : spec.valueAxis.label;
  if (sideTitle) axisTitles.push({ key: "side", x: 10, y: mT + plotH / 2, text: sideTitle, rotate: true });
  if (bottomTitle) axisTitles.push({ key: "bottom", x: mL + plotW / 2, y: height - 4, text: bottomTitle, rotate: false });

  // ---- reference lines ----
  const references = percent
    ? []
    : spec.referenceLines
        .filter((r) => r.value >= d0 && r.value <= d1)
        .map((r) => {
          const p = toPx(r.value);
          const text = r.label ? `${r.label} · ${valueFmt(r.value)}` : undefined;
          return {
            line: isV ? { x1: mL, x2: mL + plotW, y1: p, y2: p } : { x1: p, x2: p, y1: mT, y2: mT + plotH },
            label: text
              ? isV
                ? { x: mL + plotW, y: p - 5, textAnchor: "end" as const, text }
                : { x: p, y: mT - 6, textAnchor: "middle" as const, text }
              : undefined,
          };
        });

  // ---- hit bands + tooltip anchors ----
  const bands = rows.map((_, i) =>
    isV ? { x: catStart(i), y: mT, width: band, height: plotH } : { x: mL, y: catStart(i), width: plotW, height: band },
  );
  const tooltips = rows.map((_, i) => {
    const mid = catStart(i) + band / 2;
    if (isV) {
      const side = mid < width * 0.25 ? "0%" : mid > width * 0.75 ? "-100%" : "-50%";
      return { x: mid, y: Math.max(0, tips[i].min - 10), transform: `translate(${side}, -100%)` };
    }
    const right = tips[i].max + 12;
    return right > width * 0.6
      ? { x: tips[i].max - 12, y: mid, transform: "translate(-100%, -50%)" }
      : { x: right, y: mid, transform: "translate(0, -50%)" };
  });

  return { height, ticks, baseline, bars, valueLabels, categoryLabels, axisTitles, references, bands, tooltips };
}

/** A bar with a rounded data-end (at `tip`) and a square end at the baseline. */
function barPath(vertical: boolean, c0: number, c1: number, base: number, tip: number, radius: number): string {
  const r = Math.max(0, Math.min(radius, (c1 - c0) / 2, Math.abs(tip - base)));
  const f = (n: number) => Math.round(n * 100) / 100;
  if (vertical) {
    const s = tip < base ? 1 : -1;
    return `M${f(c0)},${f(base)}L${f(c0)},${f(tip + s * r)}Q${f(c0)},${f(tip)} ${f(c0 + r)},${f(tip)}L${f(c1 - r)},${f(tip)}Q${f(c1)},${f(tip)} ${f(c1)},${f(tip + s * r)}L${f(c1)},${f(base)}Z`;
  }
  const s = tip > base ? -1 : 1;
  return `M${f(base)},${f(c0)}L${f(tip + s * r)},${f(c0)}Q${f(tip)},${f(c0)} ${f(tip)},${f(c0 + r)}L${f(tip)},${f(c1 - r)}Q${f(tip)},${f(c1)} ${f(tip + s * r)},${f(c1)}L${f(base)},${f(c1)}Z`;
}

function describe(spec: ResolvedBarChartSpec, names: string[]): string {
  const what = spec.title ?? "Bar chart";
  return `${what}. ${spec.categories.length} categories${names.length > 1 ? `, series: ${names.join(", ")}` : ""}. Use arrow keys to move between categories.`;
}

