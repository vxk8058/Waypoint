import { useMemo } from "react";
import { useChartWarnings } from "../charts/shared/hooks";
import { InlineText } from "./inline-text";
import {
  normalizeCalloutSpec,
  normalizeHeadingSpec,
  normalizeListSpec,
  normalizeParagraphSpec,
  normalizeStatsSpec,
} from "./spec";
import type { CalloutTone, StatItem } from "./spec";

export interface BlockProps {
  spec: unknown;
  onWarnings?: (warnings: string[]) => void;
  className?: string;
}

/* ---------------------------------------------------------------- heading */

// Levels sit under the page's own <h1>, so level 1 renders as <h2>.
const HEADING = {
  1: { tag: "h2", cls: "text-2xl font-semibold tracking-tight text-blue-grey-050" },
  2: { tag: "h3", cls: "text-lg font-semibold text-blue-grey-050" },
  3: { tag: "h4", cls: "text-sm font-semibold uppercase tracking-wider text-blue-grey-300" },
} as const;

export function Heading({ spec: raw, onWarnings, className = "" }: BlockProps) {
  const { spec, warnings } = useMemo(() => normalizeHeadingSpec(raw), [raw]);
  useChartWarnings("Heading", warnings, onWarnings);
  if (!spec.text) return null;
  const { tag: Tag, cls } = HEADING[spec.level];
  return (
    <Tag className={`text-balance ${cls} ${className}`}>
      <InlineText text={spec.text} />
    </Tag>
  );
}

/* -------------------------------------------------------------- paragraph */

const SIZE = { default: "text-base leading-relaxed", lead: "text-lg leading-relaxed", small: "text-sm leading-normal" };

export function Paragraph({ spec: raw, onWarnings, className = "" }: BlockProps) {
  const { spec, warnings } = useMemo(() => normalizeParagraphSpec(raw), [raw]);
  useChartWarnings("Paragraph", warnings, onWarnings);
  if (!spec.text) return null;
  const tone = spec.tone === "muted" || spec.size === "lead" ? "text-blue-grey-300" : "text-blue-grey-100";
  const paras = spec.text.split(/\n\s*\n/).map((p) => p.replace(/\s*\n\s*/g, " ").trim()).filter(Boolean);
  return (
    <div className={`max-w-prose space-y-3 text-pretty ${SIZE[spec.size]} ${tone} ${className}`}>
      {paras.map((p, i) => (
        <p key={i}>
          <InlineText text={p} />
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------- list */

export function List({ spec: raw, onWarnings, className = "" }: BlockProps) {
  const { spec, warnings } = useMemo(() => normalizeListSpec(raw), [raw]);
  useChartWarnings("List", warnings, onWarnings);
  if (!spec.items.length) return null;
  const Tag = spec.ordered ? "ol" : "ul";
  return (
    <Tag
      className={[
        "max-w-prose space-y-1.5 pl-5 text-base leading-relaxed text-blue-grey-100",
        spec.ordered ? "list-decimal marker:text-blue-grey-400 marker:tabular-nums" : "list-disc marker:text-blue-grey-500",
        className,
      ].join(" ")}
    >
      {spec.items.map((item, i) => (
        <li key={i} className="pl-1">
          <InlineText text={item} />
        </li>
      ))}
    </Tag>
  );
}

/* ---------------------------------------------------------------- callout */

// Status colours: always paired with an icon and a label, never colour alone.
const CALLOUT: Record<CalloutTone, { box: string; icon: string; label: string; path: string }> = {
  info: {
    box: "border-light-blue-vivid-700/60 bg-light-blue-vivid-900/20",
    icon: "text-light-blue-vivid-300",
    label: "Note",
    path: "M12 16v-4m0-4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  },
  success: {
    box: "border-teal-700/60 bg-teal-900/20",
    icon: "text-teal-300",
    label: "Good news",
    path: "m9 12 2 2 4-4m7 2a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  },
  warning: {
    box: "border-yellow-vivid-700/60 bg-yellow-vivid-900/20",
    icon: "text-yellow-vivid-300",
    label: "Heads up",
    path: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  },
  danger: {
    box: "border-red-vivid-700/60 bg-red-vivid-900/20",
    icon: "text-red-vivid-300",
    label: "Warning",
    path: "M12 8v4m0 4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  },
};

export function Callout({ spec: raw, onWarnings, className = "" }: BlockProps) {
  const { spec, warnings } = useMemo(() => normalizeCalloutSpec(raw), [raw]);
  useChartWarnings("Callout", warnings, onWarnings);
  if (!spec.text && !spec.title) return null;
  const t = CALLOUT[spec.tone];
  return (
    <aside role={spec.tone === "danger" || spec.tone === "warning" ? "alert" : "note"} className={`flex gap-3 rounded-xl border p-4 ${t.box} ${className}`}>
      <svg aria-hidden viewBox="0 0 24 24" className={`mt-0.5 size-5 shrink-0 ${t.icon}`} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d={t.path} />
      </svg>
      <div className="min-w-0 space-y-1 text-sm leading-relaxed">
        <p className="font-semibold text-blue-grey-050">{spec.title ?? t.label}</p>
        {spec.text && (
          <p className="text-blue-grey-200">
            <InlineText text={spec.text} />
          </p>
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ stats */

export function Stats({ spec: raw, onWarnings, className = "" }: BlockProps) {
  const { spec, warnings } = useMemo(() => normalizeStatsSpec(raw), [raw]);
  useChartWarnings("Stats", warnings, onWarnings);
  if (!spec.items.length) return null;
  return (
    <dl className={`grid gap-3 ${spec.items.length === 1 ? "" : "grid-cols-2"} ${spec.items.length >= 3 ? "lg:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]" : ""} ${className}`}>
      {spec.items.map((s, i) => (
        <StatTile key={i} {...s} />
      ))}
    </dl>
  );
}

const SENTIMENT = { positive: "text-teal-300", negative: "text-red-vivid-300", neutral: "text-blue-grey-300" };

function StatTile({ label, value, change, direction, sentiment, caption }: StatItem) {
  return (
    <div className="min-w-0 rounded-xl border border-blue-grey-800 bg-surface p-4">
      <dt className="truncate text-sm text-blue-grey-300">{label}</dt>
      <dd className="mt-1 truncate text-2xl font-semibold tabular-nums tracking-tight text-blue-grey-050">{value}</dd>
      {(change || caption) && (
        <dd className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs">
          {change && (
            <span className={`inline-flex items-center gap-0.5 font-medium tabular-nums ${SENTIMENT[sentiment]}`}>
              {direction && direction !== "flat" && (
                <svg aria-hidden viewBox="0 0 12 12" className="size-3" fill="currentColor">
                  <path d={direction === "up" ? "M6 2 11 9H1z" : "M6 10 1 3h10z"} />
                </svg>
              )}
              <span className="sr-only">{direction === "up" ? "Up" : direction === "down" ? "Down" : "Unchanged"} </span>
              {change}
            </span>
          )}
          {caption && <span className="text-blue-grey-500">{caption}</span>}
        </dd>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- divider */

export function Divider({ className = "" }: BlockProps) {
  return <hr className={`border-0 border-t border-blue-grey-800 ${className}`} />;
}
