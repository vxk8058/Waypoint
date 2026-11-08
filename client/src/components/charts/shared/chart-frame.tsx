import { useState } from "react";
import { useElementWidth } from "./hooks";
import type { ReactNode } from "react";
import { SERIES_COLORS } from "./palette";
import type { SeriesColor } from "./types";

export interface LegendItem {
  name: string;
  color: SeriesColor;
  off?: boolean;
  /** Extra text after the name, e.g. a value and share for a pie slice. */
  detail?: string;
}

export interface ChartTable {
  columns: string[];
  /** Pre-formatted cells. The first column is the row header. */
  rows: string[][];
  /** Column indices that hold numbers (right-aligned, tabular figures). */
  numeric?: number[];
}

export interface ChartFrameProps {
  title?: string;
  subtitle?: string;
  className?: string;
  loading?: boolean;
  empty: boolean;
  emptyMessage: string;
  emptyHeight?: number;
  legend?: {
    items: LegendItem[];
    /** Mirror the mark: rect for bars/areas, line for lines, dot for points. */
    shape?: "rect" | "line" | "dot";
    onToggle?: (name: string) => void;
    onHover?: (name: string | null) => void;
  } | null;
  table: ChartTable;
  /** Renders the plot once the container width is known. */
  children: (width: number) => ReactNode;
}

/**
 * The card every chart sits in: title, table toggle, legend, empty state,
 * loading dim, and a table view that is always present for screen readers.
 */
export function ChartFrame({
  title,
  subtitle,
  className = "",
  loading = false,
  empty,
  emptyMessage,
  emptyHeight = 240,
  legend,
  table,
  children,
}: ChartFrameProps) {
  const [showTable, setShowTable] = useState(false);
  const [ref, width] = useElementWidth<HTMLDivElement>();

  return (
    <figure
      className={["m-0 rounded-xl border border-blue-grey-800 bg-surface p-5 transition-opacity", loading ? "opacity-50" : "", className]
        .filter(Boolean)
        .join(" ")}
      aria-busy={loading || undefined}
    >
      <header className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          {title && <h3 className="text-base font-semibold text-blue-grey-050">{title}</h3>}
          {subtitle && <p className="mt-0.5 text-sm text-blue-grey-300">{subtitle}</p>}
        </div>
        {!empty && (
          <div role="group" aria-label="View" className="flex shrink-0 gap-0.5 rounded-lg border border-blue-grey-800 p-0.5">
            <ViewButton label="Chart view" active={!showTable} onClick={() => setShowTable(false)}>
              <path d="M4 4v16h16" />
              <path d="m7 15 4-5 3 3 5-6" />
            </ViewButton>
            <ViewButton label="Table view" active={showTable} onClick={() => setShowTable(true)}>
              <rect x="3.5" y="5" width="17" height="14" rx="2" />
              <path d="M3.5 10h17M12 10v9" />
            </ViewButton>
          </div>
        )}
      </header>

      {legend && legend.items.length > 0 && !showTable && !empty && <Legend {...legend} />}

      <div ref={ref} className="relative">
        {empty ? (
          <div
            className="flex items-center justify-center rounded-lg border border-dashed border-blue-grey-800 text-sm text-blue-grey-500"
            style={{ height: emptyHeight }}
          >
            {emptyMessage}
          </div>
        ) : (
          width > 0 && !showTable && children(width)
        )}

        {!empty && (
          <div className={showTable ? "max-h-96 overflow-auto" : "sr-only"}>
            <table className="w-full text-sm">
              {title && <caption className="sr-only">{title}</caption>}
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-blue-grey-800 text-left text-xs text-blue-grey-400">
                  {table.columns.map((c, i) => (
                    <th key={i} className={["py-2 pr-4 font-medium", table.numeric?.includes(i) ? "text-right" : ""].join(" ")}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, r) => (
                  <tr key={r} className="border-b border-blue-grey-800/60 last:border-0">
                    {row.map((cell, i) =>
                      i === 0 ? (
                        <th key={i} scope="row" className="py-2 pr-4 text-left font-normal text-blue-grey-300">
                          {cell}
                        </th>
                      ) : (
                        <td key={i} className={["py-2 pr-4 text-blue-grey-050", table.numeric?.includes(i) ? "text-right tabular-nums" : ""].join(" ")}>
                          {cell}
                        </td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </figure>
  );
}

function ViewButton({ label, active, onClick, children }: { label: string; active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      className={[
        "grid size-7 cursor-pointer place-items-center rounded-md transition-colors focus-visible:outline-2 focus-visible:outline-purple-400",
        active ? "bg-surface-raised text-purple-300" : "text-blue-grey-400 hover:text-blue-grey-050",
      ].join(" ")}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="size-4">
        {children}
      </svg>
    </button>
  );
}

function Legend({ items, shape = "rect", onToggle, onHover }: NonNullable<ChartFrameProps["legend"]>) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Legend">
      {items.map((item) => {
        const swatch = (
          <span
            aria-hidden
            className={shape === "line" ? "h-0.5 w-3.5 rounded-full" : shape === "dot" ? "size-2.5 rounded-full" : "size-2.5 rounded-sm"}
            style={{ background: SERIES_COLORS[item.color].fill }}
          />
        );
        const content = (
          <>
            {swatch}
            <span>{item.name}</span>
            {item.detail && <span className="tabular-nums text-blue-grey-500">{item.detail}</span>}
          </>
        );
        return (
          <li key={item.name} onPointerEnter={() => onHover?.(item.name)} onPointerLeave={() => onHover?.(null)}>
            {onToggle ? (
              <button
                type="button"
                onClick={() => onToggle(item.name)}
                onFocus={() => onHover?.(item.name)}
                onBlur={() => onHover?.(null)}
                aria-pressed={!item.off}
                title={item.off ? `Show ${item.name}` : `Hide ${item.name}`}
                className={[
                  "flex cursor-pointer items-center gap-1.5 rounded text-xs text-blue-grey-300 transition-opacity hover:text-blue-grey-050 focus-visible:outline-2 focus-visible:outline-purple-400",
                  item.off ? "opacity-40" : "",
                ].join(" ")}
              >
                {content}
              </button>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-blue-grey-300">{content}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
