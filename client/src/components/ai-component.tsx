import type { ComponentType } from "react";
import { BarChart, GanttChart, Histogram, LineChart, PieChart, ScatterPlot } from "./charts";

/**
 * What the AI backend sends for each visual block:
 *   { "type": "bar_chart", "props": { ...BarChartSpec } }
 *
 * Each type's props are described by the matching `*.schema.json` under
 * charts/, ready to use as the backend tool definition.
 *
 * Add new AI-callable components to `registry`; the `type` key is the name the
 * model uses in its tool call.
 */
export interface AiBlock {
  type: string;
  props?: unknown;
}

interface AiRenderableProps {
  spec: unknown;
  onWarnings?: (warnings: string[]) => void;
}

const registry: Record<string, ComponentType<AiRenderableProps>> = {
  bar_chart: BarChart,
  line_chart: LineChart,
  histogram: Histogram,
  pie_chart: PieChart,
  scatter_plot: ScatterPlot,
  gantt_chart: GanttChart,
};

export interface AiComponentProps {
  block: AiBlock;
  className?: string;
  onWarnings?: (type: string, warnings: string[]) => void;
}

export function AiComponent({ block, className, onWarnings }: AiComponentProps) {
  const Component = registry[block?.type];
  if (!Component) {
    if (import.meta.env.DEV) console.warn(`[AiComponent] unknown block type "${block?.type}"`);
    return null;
  }
  return (
    <div className={className}>
      <Component spec={block.props} onWarnings={onWarnings && ((w) => onWarnings(block.type, w))} />
    </div>
  );
}

export default AiComponent;
