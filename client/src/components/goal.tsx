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

// Solid surface fill inside the padding box, gradient showing through the transparent border.
const gradientBorder = [
  "linear-gradient(var(--color-surface), var(--color-surface)) padding-box",
  "linear-gradient(to right, var(--color-purple-400), var(--color-light-blue-vivid-400), var(--color-teal-300)) border-box",
].join(", ");

export interface GoalProps {
  title?: string;
  className?: string;
}

export function Goal({ title = "Buy a new car for Christmas", className = "" }: GoalProps) {
  return (
    <section
      aria-label="Goal"
      className={[
        "mx-auto flex h-12 w-full max-w-2xl select-none items-center gap-3 rounded-full border-2 border-transparent px-5 text-blue-grey-400",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ background: gradientBorder }}
    >
      <TargetIcon />
      <span className="truncate text-base font-semibold tracking-normal text-blue-grey-100">{title}</span>
    </section>
  );
}

export default Goal;
