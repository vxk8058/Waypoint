import { isObject } from "./charts/shared/coerce";

/** What the backend sends for each piece of a response. */
export interface AiBlock {
  type: string;
  props?: unknown;
}

export interface NormalizedBlock {
  type: string;
  props: unknown;
  /** Only for type "row". */
  row?: { blocks: unknown[]; columns: 1 | 2 | 3 };
}

// Names a model is likely to reach for → the registry key.
const ALIASES: Record<string, string> = {
  h1: "heading",
  h2: "heading",
  h3: "heading",
  h4: "heading",
  title: "heading",
  header: "heading",
  text: "paragraph",
  p: "paragraph",
  markdown: "paragraph",
  body: "paragraph",
  bullets: "list",
  bullet_list: "list",
  ul: "list",
  ol: "list",
  numbered_list: "list",
  note: "callout",
  alert: "callout",
  insight: "callout",
  stat: "stats",
  kpi: "stats",
  kpis: "stats",
  metrics: "stats",
  hr: "divider",
  separator: "divider",
  columns: "row",
  grid: "row",
  group: "row",
  bar: "bar_chart",
  bar_graph: "bar_chart",
  barchart: "bar_chart",
  line: "line_chart",
  line_graph: "line_chart",
  linechart: "line_chart",
  pie: "pie_chart",
  donut: "pie_chart",
  donut_chart: "pie_chart",
  piechart: "pie_chart",
  scatter: "scatter_plot",
  scatterplot: "scatter_plot",
  scatter_chart: "scatter_plot",
  gantt: "gantt_chart",
  timeline: "gantt_chart",
  histogram_chart: "histogram",
};

/**
 * Forgiving: accepts a bare string (paragraph), `props` nested or flattened
 * onto the block, `component`/`kind` instead of `type`, and common aliases
 * ("h2", "bar_graph", "kpis"…). Returns null for anything unusable.
 */
export function normalizeBlock(raw: unknown): NormalizedBlock | null {
  if (typeof raw === "string") return raw.trim() ? { type: "paragraph", props: { text: raw } } : null;
  if (!isObject(raw)) return null;

  const rawType = raw.type ?? raw.component ?? raw.kind ?? raw.block;
  if (typeof rawType !== "string") return null;
  const key = rawType.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const type = ALIASES[key] ?? key;

  const { type: _t, component: _c, kind: _k, block: _b, props, ...rest } = raw;
  let p: unknown = isObject(props) ? { ...rest, ...props } : props !== undefined ? props : rest;

  // "h2" carries its level in the type.
  const hLevel = /^h([1-4])$/.exec(key);
  if (hLevel && isObject(p) && p.level === undefined) p = { ...p, level: Number(hLevel[1]) };
  if ((key === "ol" || key === "numbered_list") && isObject(p)) p = { ...p, ordered: true };

  if (type === "row") {
    const o = isObject(p) ? p : {};
    const list = Array.isArray(p) ? p : Array.isArray(o.blocks) ? o.blocks : Array.isArray(o.items) ? o.items : Array.isArray(o.children) ? o.children : [];
    // Rows don't nest: inner rows are flattened.
    const blocks = list.flatMap((b) => {
      const n = normalizeBlock(b);
      return n?.type === "row" ? n.row!.blocks : n ? [b] : [];
    });
    const asked = typeof o.columns === "number" ? Math.round(o.columns) : blocks.length;
    const columns = Math.min(3, Math.max(1, asked)) as 1 | 2 | 3;
    return { type, props: p, row: { blocks, columns } };
  }

  return { type, props: p };
}

/** Accepts an array of blocks, `{ blocks: [...] }`, or a JSON string of either. */
export function toBlockList(input: unknown): unknown[] {
  let v = input;
  if (typeof input === "string") {
    try {
      v = JSON.parse(input);
    } catch {
      // Plain prose: show it as one paragraph.
      return input.trim() ? [input] : [];
    }
  }
  if (Array.isArray(v)) return v;
  if (isObject(v)) {
    if (Array.isArray(v.blocks)) return v.blocks;
    if (Array.isArray(v.content)) return v.content;
    if (v.type !== undefined) return [v];
  }
  return [];
}
