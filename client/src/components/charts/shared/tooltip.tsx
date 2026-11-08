import { SERIES_COLORS } from "./palette";
import type { SeriesColor } from "./types";

export interface TooltipRow {
  /** Series colour for the line key; omit for plain rows. */
  color?: SeriesColor;
  /** The strong part: the number the reader came for. */
  value: string;
  /** Secondary: series name or field name. */
  label?: string;
  /** Muted extra, e.g. "(42%)". */
  extra?: string;
}

export interface TooltipProps {
  x: number;
  y: number;
  /** CSS transform used to anchor the box relative to (x, y). */
  transform?: string;
  title?: string;
  rows: TooltipRow[];
  footer?: TooltipRow;
}

/** Values lead, labels follow; series keyed with a short line, never a box. */
export function ChartTooltip({ x, y, transform = "translate(-50%, calc(-100% - 10px))", title, rows, footer }: TooltipProps) {
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 min-w-36 max-w-72 rounded-lg border border-blue-grey-700 bg-surface-raised px-3 py-2 shadow-lg shadow-black/40"
      style={{ left: x, top: y, transform }}
    >
      {title && <p className="mb-1.5 text-xs text-blue-grey-300">{title}</p>}
      <ul className="space-y-1">
        {rows.map((r, i) => (
          <Row key={i} {...r} />
        ))}
        {footer && (
          <li className="mt-1 border-t border-blue-grey-700 pt-1">
            <Row {...footer} asDiv />
          </li>
        )}
      </ul>
    </div>
  );
}

function Row({ color, value, label, extra, asDiv }: TooltipRow & { asDiv?: boolean }) {
  const Tag = asDiv ? "div" : "li";
  return (
    <Tag className="flex items-center gap-2 text-sm">
      {color ? (
        <span aria-hidden className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: SERIES_COLORS[color].fill }} />
      ) : (
        <span aria-hidden className="w-3 shrink-0" />
      )}
      <span className="font-semibold whitespace-nowrap tabular-nums text-blue-grey-050">
        {value}
        {extra && <span className="ml-1 font-normal text-blue-grey-300">{extra}</span>}
      </span>
      {label && <span className="truncate text-blue-grey-300">{label}</span>}
    </Tag>
  );
}
