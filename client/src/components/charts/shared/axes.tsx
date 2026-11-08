import { CHART_TOKENS } from "./palette";
import { FONT, HALO } from "./layout";
import type { Plot, Tick } from "./layout";


interface CartesianAxesProps {
  plot: Plot;
  xTicks?: Tick[];
  yTicks?: Tick[];
  xGrid?: boolean;
  yGrid?: boolean;
  xTitle?: string;
  yTitle?: string;
  /** Put x labels above the plot (gantt) instead of below. */
  xOnTop?: boolean;
  /** Total SVG height, so the bottom title can sit on the last line. */
  height: number;
}

/** Hairline solid gridlines, muted tick labels, optional axis titles. */
export function CartesianAxes({ plot, xTicks = [], yTicks = [], xGrid = false, yGrid = true, xTitle, yTitle, xOnTop = false, height }: CartesianAxesProps) {
  const { left, top, width: w, height: h } = plot;
  return (
    <g fontSize={FONT}>
      {yGrid &&
        yTicks.map((t) => (
          <line key={`yg${t.pos}`} x1={left} x2={left + w} y1={t.pos} y2={t.pos} stroke={CHART_TOKENS.grid} strokeWidth={1} shapeRendering="crispEdges" />
        ))}
      {xGrid &&
        xTicks.map((t) => (
          <line key={`xg${t.pos}`} x1={t.pos} x2={t.pos} y1={top} y2={top + h} stroke={CHART_TOKENS.grid} strokeWidth={1} shapeRendering="crispEdges" />
        ))}
      {yTicks.map((t) => (
        <text key={`yt${t.pos}`} x={left - 10} y={t.pos + 4} textAnchor="end" fill={CHART_TOKENS.textMuted} style={{ fontVariantNumeric: "tabular-nums" }}>
          {t.text}
        </text>
      ))}
      {xTicks.map((t) => (
        <text
          key={`xt${t.pos}`}
          x={t.pos}
          y={xOnTop ? top - 8 : top + h + 18}
          textAnchor="middle"
          fill={CHART_TOKENS.textMuted}
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {t.text}
        </text>
      ))}
      {yTitle && (
        <text x={10} y={top + h / 2} transform={`rotate(-90 10 ${top + h / 2})`} textAnchor="middle" fill={CHART_TOKENS.textMuted} fontSize={11}>
          {yTitle}
        </text>
      )}
      {xTitle && (
        <text x={left + w / 2} y={height - 4} textAnchor="middle" fill={CHART_TOKENS.textMuted} fontSize={11}>
          {xTitle}
        </text>
      )}
    </g>
  );
}

interface ReferenceRuleProps {
  orientation: "horizontal" | "vertical";
  pos: number;
  plot: Plot;
  label?: string;
  /** Where a horizontal rule's label sits. "start" keeps it clear of end-of-line labels. */
  align?: "start" | "end";
  /** Lift a vertical rule's label by this many px (to stagger neighbours). */
  labelOffset?: number;
}

/** A dashed rule for a target, budget, mean… labelled at its end. */
export function ReferenceRule({ orientation, pos, plot, label, align = "end", labelOffset = 0 }: ReferenceRuleProps) {
  const h = orientation === "horizontal";
  return (
    <g pointerEvents="none">
      <line
        x1={h ? plot.left : pos}
        x2={h ? plot.left + plot.width : pos}
        y1={h ? pos : plot.top}
        y2={h ? pos : plot.top + plot.height}
        stroke={CHART_TOKENS.reference}
        strokeWidth={1}
        strokeDasharray="4 3"
        shapeRendering="crispEdges"
      />
      {label && (
        <text
          x={h ? (align === "start" ? plot.left + 4 : plot.left + plot.width) : pos}
          y={h ? pos - 5 : plot.top - 6 - labelOffset}
          textAnchor={h ? (align === "start" ? "start" : "end") : "middle"}
          fill={CHART_TOKENS.textSecondary}
          fontSize={11}
          {...HALO}
        >
          {label}
        </text>
      )}
    </g>
  );
}
