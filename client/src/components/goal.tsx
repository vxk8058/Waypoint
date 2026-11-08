import type { ReactNode, SVGProps } from "react";
import { fetchGoal, goalProgress, parseDate, type GoalStatus, type SavingsGoal } from "../lib/goal";
import { useAsync } from "../lib/use-async";

const brandGradient = "linear-gradient(to right, var(--color-purple-400), var(--color-light-blue-vivid-400), var(--color-teal-300))";

// Solid surface fill inside the padding box, gradient showing through the transparent border.
const gradientBorder = [
  "linear-gradient(var(--color-surface), var(--color-surface)) padding-box",
  `${brandGradient} border-box`,
].join(", ");

/** Number of slanted sections in the progress bar. */
const SEGMENTS = 20;

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const monthYear = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

// ---------- icons ----------

function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="size-5 shrink-0" {...props}>
      {children}
    </svg>
  );
}

const goalIcons: Record<string, ReactNode> = {
  vehicle: (
    <Icon>
      <path d="M5 17H3v-5l2-5h14l2 5v5h-2" />
      <path d="M3 12h18" />
      <circle cx="7.5" cy="17" r="2" />
      <circle cx="16.5" cy="17" r="2" />
      <path d="M9.5 17h5" />
    </Icon>
  ),
  emergency_fund: (
    <Icon>
      <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  ),
  tuition: (
    <Icon>
      <path d="M2 9l10-5 10 5-10 5L2 9Z" />
      <path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5" />
      <path d="M22 9v6" />
    </Icon>
  ),
  relocation: (
    <Icon>
      <path d="M3 11l9-7 9 7" />
      <path d="M5 10v10h14V10" />
      <path d="M10 20v-6h4v6" />
    </Icon>
  ),
};

const defaultIcon = (
  <Icon>
    <path d="M5 21V4" />
    <path d="M5 4h12l-2 4 2 4H5" />
  </Icon>
);

// ---------- status badge ----------

const statusStyles: Record<GoalStatus, { label: string; className: string }> = {
  reached: { label: "Goal reached", className: "bg-teal-400/15 text-teal-200" },
  ahead: { label: "Ahead of schedule", className: "bg-teal-400/15 text-teal-200" },
  "on-track": { label: "On track", className: "bg-light-blue-vivid-400/15 text-light-blue-vivid-200" },
  behind: { label: "Behind", className: "bg-yellow-vivid-400/15 text-yellow-vivid-200" },
  stalled: { label: "No contributions", className: "bg-yellow-vivid-400/15 text-yellow-vivid-200" },
};

// ---------- bar ----------

export interface GoalBarProps {
  goal: SavingsGoal;
  /** Date the balances are from. */
  asOf: Date;
  className?: string;
}

export function GoalBar({ goal, asOf, className = "" }: GoalBarProps) {
  const { pct, status, projected } = goalProgress(goal, asOf);
  // Fill whole segments only; any progress above 0 lights at least one.
  const filled = pct === 0 ? 0 : Math.max(1, Math.round((pct / 100) * SEGMENTS));

  const badge = statusStyles[status];
  const badgeTitle = projected
    ? `Projected to finish ${monthYear.format(projected)}, target ${monthYear.format(parseDate(goal.target_date))}`
    : undefined;

  return (
    <section
      aria-label="Goal"
      className={["flex w-full select-none flex-col gap-2 rounded-lg border-2 border-transparent px-5 py-3 text-blue-grey-400", className]
        .filter(Boolean)
        .join(" ")}
      style={{ background: gradientBorder }}
    >
      <div className="flex items-center gap-3">
        <span className="text-blue-grey-200">{goalIcons[goal.goal_type] ?? defaultIcon}</span>
        <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2">
          <span className="truncate text-base font-semibold text-blue-grey-100">{goal.name}</span>
          <span className="text-sm">by {monthYear.format(parseDate(goal.target_date))}</span>
        </div>
        <span title={badgeTitle} className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${badge.className}`}>
          {badge.label}
          {projected && status !== "on-track" && <span className="font-normal"> · {monthYear.format(projected)}</span>}
        </span>
      </div>

      <div
        role="progressbar"
        aria-label={`${goal.name} progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
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

      <p className="text-sm tabular-nums">
        <span className="font-semibold text-blue-grey-100">{dollars.format(goal.current_saved)}</span> of{" "}
        {dollars.format(goal.target_amount)} · {Math.round(pct)}%
      </p>
    </section>
  );
}

// ---------- data-connected wrapper ----------

/** Goal bar for the signed-in user, loaded from GET /api/me/goal. */
export function Goal({ className = "" }: { className?: string }) {
  const { data, error, loading } = useAsync(fetchGoal, []);

  if (loading && !data) {
    return <div aria-hidden="true" className={`h-[6.5rem] w-full animate-pulse rounded-lg bg-surface ${className}`} />;
  }
  if (error || !data) {
    return (
      <p role="alert" className={`rounded-lg bg-surface px-5 py-3 text-sm text-blue-grey-300 ${className}`}>
        Couldn't load your goal: {error?.message ?? "no data"}
      </p>
    );
  }
  return <GoalBar goal={data.goal} asOf={parseDate(data.data.as_of_date)} className={className} />;
}

export default Goal;
