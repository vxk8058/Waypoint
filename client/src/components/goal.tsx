const brandGradient = "linear-gradient(to right, var(--color-purple-400), var(--color-light-blue-vivid-400), var(--color-teal-300))";

// Solid surface fill inside the padding box, gradient showing through the transparent border.
const gradientBorder = [
  "linear-gradient(var(--color-surface), var(--color-surface)) padding-box",
  `${brandGradient} border-box`,
].join(", ");

/** Number of slanted sections in the progress bar. */
const SEGMENTS = 20;

export interface GoalProps {
  title?: string;
  /** Completion percentage, 0–100. */
  progress?: number;
  className?: string;
}

export function Goal({ title = "Goal: Buy a new car for Christmas", progress = 40, className = "" }: GoalProps) {
  const pct = Math.min(100, Math.max(0, progress));
  // Fill whole segments only; any progress above 0 lights at least one.
  const filled = pct === 0 ? 0 : Math.max(1, Math.round((pct / 100) * SEGMENTS));

  return (
    <section
      aria-label="Goal"
      className={[
        "flex w-full select-none items-center gap-3 rounded-lg border-2 border-transparent px-5 py-3 text-blue-grey-400",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ background: gradientBorder }}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <span className="truncate text-base font-semibold tracking-normal text-blue-grey-100">{title}</span>
        <div
          role="progressbar"
          aria-label={`${title} progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          // Slanted segments; overflow-hidden cuts the first and last ones flat at the ends.
          className="flex h-3 w-full gap-1 overflow-hidden"
        >
          {Array.from({ length: SEGMENTS }, (_, i) => (
            <span key={i} className="relative h-full flex-1 -skew-x-[30deg] bg-blue-grey-800">
              {/* Each segment shows its slice of one full-width gradient, so the colors line up with the border's. */}
              <span
                className="absolute inset-0 transition-opacity duration-300 ease-out motion-reduce:transition-none"
                style={{
                  background: brandGradient,
                  backgroundSize: `${SEGMENTS * 100}% 100%`,
                  backgroundPosition: `${(i / (SEGMENTS - 1)) * 100}% 0`,
                  opacity: i < filled ? 1 : 0,
                  transitionDelay: `${i * 25}ms`,
                }}
              />
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

export default Goal;
