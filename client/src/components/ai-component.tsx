import type { ComponentType } from "react";
import { BarChart, GanttChart, Histogram, LineChart, PieChart, ScatterPlot } from "./charts";
import { BlockBoundary, Callout, Divider, Heading, List, Paragraph, Stats } from "./blocks";
import { normalizeBlock } from "./ai-blocks";
import type { AiBlock } from "./ai-blocks";

/**
 * Renders one block the AI backend sent:
 *   { "type": "bar_chart", "props": { ...BarChartSpec } }
 *   { "type": "heading",   "props": { "text": "October", "level": 1 } }
 *   { "type": "row",       "props": { "blocks": [ ...blocks side by side ] } }
 *
 * To render a whole response (text + charts in order) use <AiDocument>.
 * The full tool schema is `ai-document.schema.json` (`npm run schema` rebuilds it).
 *
 * Add new AI-callable components to `registry`; the key is the name the model
 * uses. Add it to scripts/build-ai-schema.mjs too.
 */
export type { AiBlock };

interface AiRenderableProps {
  spec: unknown;
  onWarnings?: (warnings: string[]) => void;
}

const registry: Record<string, ComponentType<AiRenderableProps>> = {
  // text
  heading: Heading,
  paragraph: Paragraph,
  list: List,
  callout: Callout,
  stats: Stats,
  divider: Divider,
  // charts
  bar_chart: BarChart,
  line_chart: LineChart,
  histogram: Histogram,
  pie_chart: PieChart,
  scatter_plot: ScatterPlot,
  gantt_chart: GanttChart,
};

export interface AiComponentProps {
  /** A block, or anything close to one; it is normalized first. */
  block: unknown;
  className?: string;
  onWarnings?: (type: string, warnings: string[]) => void;
}

export function AiComponent({ block: raw, className, onWarnings }: AiComponentProps) {
  const block = normalizeBlock(raw);
  if (!block) {
    if (import.meta.env.DEV) console.warn("[AiComponent] unrecognized block", raw);
    return null;
  }

  if (block.type === "row") {
    const { blocks, columns } = block.row!;
    if (!blocks.length) return null;
    return (
      <div className={[ROW_COLS[columns], "grid gap-6", className].filter(Boolean).join(" ")}>
        {blocks.map((b, i) => (
          <AiComponent key={i} block={b} onWarnings={onWarnings} className="min-w-0 [&>figure]:h-full" />
        ))}
      </div>
    );
  }

  const Component = registry[block.type];
  if (!Component) {
    if (import.meta.env.DEV) console.warn(`[AiComponent] unknown block type "${block.type}"`);
    return null;
  }
  return (
    <BlockBoundary type={block.type}>
      <div className={className}>
        <Component spec={block.props} onWarnings={onWarnings && ((w) => onWarnings(block.type, w))} />
      </div>
    </BlockBoundary>
  );
}

// Full classes so Tailwind sees them. Phones always stack.
const ROW_COLS: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 md:grid-cols-2",
  3: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3",
};

export default AiComponent;
