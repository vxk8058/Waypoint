import type { SVGProps } from "react";

function TargetIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true" className="size-5 shrink-0" {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </svg>
  );
}

const brandGradient = "linear-gradient(to right, var(--color-purple-400), var(--color-light-blue-vivid-400), var(--color-teal-300))";

// Solid surface fill inside the padding box, gradient showing through the transparent border.
const gradientBorder = [
  "linear-gradient(var(--color-surface), var(--color-surface)) padding-box",
  `${brandGradient} border-box`,
].join(", ");

export interface GoalProps {
  title?: string;
  /** Completion percentage, 0–100. */
  progress?: number;
  className?: string;
}

export function Goal({ title = "Buy a new car for Christmas", progress = 40, className = "" }: GoalProps) {
  const pct = Math.min(100, Math.max(0, progress));

  return (
    <section
      aria-label="Goal"
      className={[
        "flex w-full select-none items-center gap-3 rounded-full border-2 border-transparent px-5 py-2.5 text-blue-grey-400",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ background: gradientBorder }}
    >
      <TargetIcon />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <span className="truncate text-base font-semibold tracking-normal text-blue-grey-100">{title}</span>
        <div
          role="progressbar"
          aria-label={`${title} progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          className="h-1.5 w-full overflow-hidden rounded-full bg-blue-grey-800"
        >
          {/* Gradient spans the full track and is clipped, so its colors line up with the border's. */}
          <div
            className="h-full w-full rounded-full transition-[clip-path] duration-500 ease-out"
            style={{ background: brandGradient, clipPath: `inset(0 ${100 - pct}% 0 0 round 9999px)` }}
          />
        </div>
      </div>
    </section>
  );
}

export default Goal;
