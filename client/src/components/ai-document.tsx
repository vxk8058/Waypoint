import { AiComponent } from "./ai-component";
import { normalizeBlock, toBlockList } from "./ai-blocks";

export interface AiDocumentProps {
  /**
   * The AI response: `{ "blocks": [...] }`, a bare array of blocks, or a JSON
   * string of either. Blocks render top to bottom in the order sent.
   */
  document: unknown;
  className?: string;
  onWarnings?: (type: string, warnings: string[]) => void;
}

/**
 * Text and charts mixed freely, e.g.
 *   heading → bar_chart → heading → paragraph → pie_chart
 * Use a `row` block to put several charts side by side.
 */
export function AiDocument({ document, className = "", onWarnings }: AiDocumentProps) {
  const blocks = toBlockList(document);
  return (
    <article className={`flex flex-col gap-4 ${className}`}>
      {blocks.map((b, i) => {
        const type = normalizeBlock(b)?.type;
        // Headings open a new section: extra room above (not before the first block).
        const spacing = type === "heading" && i > 0 ? (headingLevel(b) === 1 ? "mt-6" : "mt-3") : "";
        return <AiComponent key={i} block={b} className={spacing || undefined} onWarnings={onWarnings} />;
      })}
    </article>
  );
}

function headingLevel(b: unknown) {
  const n = normalizeBlock(b);
  const p = n?.props as { level?: unknown } | undefined;
  return Number(p?.level ?? 1);
}

export default AiDocument;
