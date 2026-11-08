/** Layout constants and helpers shared by the chart renderers. */

export const FONT = 12;
/** A surface-coloured outline so text stays legible where it crosses a line or mark. */
export const HALO = { stroke: "var(--color-surface)", strokeWidth: 3, strokeLinejoin: "round", paintOrder: "stroke" } as const;

export interface Plot {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Tick {
  pos: number; // pixel
  text: string;
}

/** Drop tick labels that would overlap their neighbour. */
export function thinTicks(ticks: Tick[], measure: (t: string) => number, gap = 16): Tick[] {
  if (ticks.length < 3) return ticks;
  for (let every = 1; every < ticks.length; every++) {
    const kept = ticks.filter((_, i) => i % every === 0);
    const ok = kept.every((t, i) => i === 0 || t.pos - kept[i - 1].pos >= (measure(t.text) + measure(kept[i - 1].text)) / 2 + gap);
    if (ok) return kept;
  }
  return [ticks[0]];
}

/** Keep a tooltip inside the chart: flip/shift the anchor near the edges. */
export function anchorAbove(x: number, y: number, width: number) {
  const side = x < width * 0.2 ? "0%" : x > width * 0.8 ? "-100%" : "-50%";
  return { x, y, transform: `translate(${side}, calc(-100% - 10px))` };
}

export function anchorBeside(x: number, y: number, width: number) {
  return x > width * 0.6
    ? { x: x - 14, y, transform: "translate(-100%, -50%)" }
    : { x: x + 14, y, transform: "translate(0, -50%)" };
}
