import { useEffect, useLayoutEffect, useRef, useState } from "react";

export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(Math.floor(el.getBoundingClientRect().width));
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Report normaliser warnings once per spec change (and to the console in dev). */
export function useChartWarnings(name: string, warnings: string[], onWarnings?: (w: string[]) => void) {
  const cb = useRef(onWarnings);
  useLayoutEffect(() => {
    cb.current = onWarnings;
  });
  useEffect(() => {
    if (!warnings.length) return;
    cb.current?.(warnings);
    if (import.meta.env.DEV) console.warn(`[${name}] spec adjusted:`, warnings);
  }, [name, warnings]);
}

/** Toggle a series off/on, never hiding the last visible one. */
export function useHiddenSeries(total: number) {
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const toggle = (name: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else if (total - next.size > 1) next.add(name);
      return next;
    });
  return [hidden, toggle] as const;
}
