import { useChartWarnings } from "../shared/hooks";
import { useMemo, useState } from "react";
import { ChartFrame } from "../shared/chart-frame";
import { SERIES_COLORS } from "../shared/palette";
import { makeFormatter } from "../shared/scale";
import { ChartTooltip } from "../shared/tooltip";
import { normalizePieChartSpec } from "./spec";
import type { PieChartSpec, ResolvedSlice } from "./spec";

export interface PieChartProps {
  spec: PieChartSpec | unknown;
  className?: string;
  loading?: boolean;
  onWarnings?: (warnings: string[]) => void;
  onSliceClick?: (slice: { label: string; value: number; share: number; folded?: string[] }) => void;
}

const GAP = 2; // px surface gap between slices
const MAX_D = 220;

export function PieChart({ spec: input, className = "", loading = false, onWarnings, onSliceClick }: PieChartProps) {
  const { spec, warnings } = useMemo(() => normalizePieChartSpec(input), [input]);
  useChartWarnings("PieChart", warnings, onWarnings);
  const [active, setActive] = useState<number | null>(null);

  const fmt = useMemo(() => makeFormatter(spec.valueFormat, spec.total), [spec]);
  const pct = (s: number) => `${s < 0.01 ? "<1" : Math.round(s * 100)}%`;
  const isEmpty = spec.slices.length === 0;

  return (
    <ChartFrame
      title={spec.title}
      subtitle={spec.subtitle}
      className={className}
      loading={loading}
      empty={isEmpty}
      emptyMessage={spec.emptyMessage}
      emptyHeight={MAX_D}
      table={{
        columns: ["Part", "Value", "Share"],
        rows: [
          ...spec.slices.map((s) => [s.folded ? `Other (${s.folded.join(", ")})` : s.label, fmt(s.value), pct(s.share)]),
          ["Total", fmt(spec.total), "100%"],
        ],
        numeric: [1, 2],
      }}
    >
      {(width) => {
        const beside = width >= 420;
        const d = Math.min(MAX_D, beside ? width * 0.45 : width);
        const r = d / 2;
        const inner = spec.donut ? r * 0.62 : 0;
        const arcs = layoutArcs(spec.slices, r, inner);
        const a = active !== null ? spec.slices[active] : null;
        const centerValue = a ? fmt(a.value) : (spec.center?.value ?? fmt(spec.total));
        const centerLabel = a ? `${a.label} · ${pct(a.share)}` : (spec.center?.label ?? "Total");

        return (
          <div className={beside ? "flex items-center gap-8" : "flex flex-col items-center gap-5"}>
            <div className="relative shrink-0" style={{ width: d, height: d }}>
              <svg width={d} height={d} viewBox={`${-r} ${-r} ${d} ${d}`} role="group" aria-label={`${spec.title ?? "Pie chart"}: ${spec.slices.map((s) => `${s.label} ${pct(s.share)}`).join(", ")}`} className="block overflow-visible">
                {arcs.map((path, i) => {
                  const s = spec.slices[i];
                  return (
                    <path
                      key={s.label}
                      d={path}
                      fill={SERIES_COLORS[s.color].fill}
                      tabIndex={0}
                      role={onSliceClick ? "button" : "img"}
                      aria-label={`${s.label}: ${fmt(s.value)}, ${pct(s.share)}`}
                      opacity={active !== null && active !== i ? 0.45 : 1}
                      className={["outline-none transition-opacity duration-150 focus-visible:stroke-blue-grey-050", onSliceClick ? "cursor-pointer" : ""].join(" ")}
                      strokeWidth={2}
                      onPointerEnter={() => setActive(i)}
                      onPointerLeave={() => setActive((x) => (x === i ? null : x))}
                      onFocus={() => setActive(i)}
                      onBlur={() => setActive((x) => (x === i ? null : x))}
                      onClick={() => onSliceClick?.(s)}
                      onKeyDown={(e) => {
                        if (onSliceClick && (e.key === "Enter" || e.key === " ")) {
                          e.preventDefault();
                          onSliceClick(s);
                        }
                      }}
                    />
                  );
                })}
              </svg>
              {spec.donut && (
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center" aria-live="polite">
                  <span className="font-semibold text-blue-grey-050" style={{ fontSize: Math.max(16, Math.min(28, inner * 0.36)) }}>
                    {centerValue}
                  </span>
                  <span className="max-w-[70%] truncate text-xs text-blue-grey-300">{centerLabel}</span>
                </div>
              )}
              {!spec.donut && a && active !== null && (
                <ChartTooltip x={r} y={0} title={a.label} rows={[{ color: a.color, value: fmt(a.value), extra: `(${pct(a.share)})` }]} />
              )}
            </div>

            {/* The legend carries the figures: name, value, share */}
            <ul className={beside ? "min-w-0 flex-1 space-y-2" : "w-full space-y-2"} aria-label="Parts">
              {spec.slices.map((s, i) => (
                <li
                  key={s.label}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive((x) => (x === i ? null : x))}
                  className={["flex items-center gap-2.5 rounded-md px-2 py-1 text-sm transition-colors", active === i ? "bg-surface-raised" : ""].join(" ")}
                >
                  <span aria-hidden className="size-2.5 shrink-0 rounded-sm" style={{ background: SERIES_COLORS[s.color].fill }} />
                  <span className="min-w-0 flex-1 truncate text-blue-grey-300" title={s.folded?.join(", ")}>
                    {s.label}
                  </span>
                  <span className="font-semibold tabular-nums text-blue-grey-050">{fmt(s.value)}</span>
                  <span className="w-10 text-right tabular-nums text-blue-grey-500">{pct(s.share)}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      }}
    </ChartFrame>
  );
}

export default PieChart;

/** Arcs from 12 o'clock, clockwise, with a constant-width surface gap between slices. */
function layoutArcs(slices: ResolvedSlice[], r: number, inner: number): string[] {
  const pt = (rad: number, a: number) => `${(rad * Math.sin(a)).toFixed(2)},${(-rad * Math.cos(a)).toFixed(2)}`;
  if (slices.length === 1) {
    // A full ring can't be one arc; draw two halves.
    const ring = (rad: number, sweep: 0 | 1) => `M${pt(rad, 0)}A${rad},${rad} 0 1 ${sweep} ${pt(rad, Math.PI)}A${rad},${rad} 0 1 ${sweep} ${pt(rad, 0)}Z`;
    return [inner ? `${ring(r, 1)}${ring(inner, 0)}` : ring(r, 1)];
  }
  let a = 0;
  return slices.map((s) => {
    const span = s.share * Math.PI * 2;
    const a0 = a;
    const a1 = a + span;
    a = a1;
    const po = Math.min(span / 2, GAP / 2 / r); // half-gap as an angle at the outer edge
    const pi = inner ? Math.min(span / 2, GAP / 2 / inner) : 0;
    const large = span - 2 * po > Math.PI ? 1 : 0;
    const outer = `M${pt(r, a0 + po)}A${r},${r} 0 ${large} 1 ${pt(r, a1 - po)}`;
    if (!inner) return `${outer}L0,0Z`;
    const largeIn = span - 2 * pi > Math.PI ? 1 : 0;
    return `${outer}L${pt(inner, a1 - pi)}A${inner},${inner} 0 ${largeIn} 0 ${pt(inner, a0 + pi)}Z`;
  });
}
