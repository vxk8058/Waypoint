import { useId } from "react";
import type { ComponentProps } from "react";

type Size = "sm" | "md" | "lg";

export interface SelectProps extends Omit<ComponentProps<"select">, "size"> {
  label?: string;
  hint?: string;
  error?: string;
  size?: Size;
  fullWidth?: boolean;
  containerClassName?: string;
}

const sizes: Record<Size, string> = {
  sm: "h-8 pl-3 pr-8 text-sm",
  md: "h-10 pl-3 pr-9 text-base",
  lg: "h-12 pl-4 pr-10 text-lg",
};

// Native <select> styled to match TextField.
export function Select({
  label,
  hint,
  error,
  size = "md",
  fullWidth = false,
  id,
  required,
  className = "",
  containerClassName = "",
  children,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const messageId = `${selectId}-message`;
  const message = error ?? hint;

  const select = [
    "w-full cursor-pointer appearance-none rounded-lg border bg-canvas text-blue-grey-050 outline-none transition-colors",
    "focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-canvas",
    "disabled:cursor-not-allowed disabled:bg-surface disabled:opacity-60",
    error
      ? "border-red-vivid-400 focus-visible:ring-red-vivid-400/50"
      : "border-blue-grey-600 hover:border-blue-grey-500 focus-visible:border-purple-400 focus-visible:ring-purple-400/40",
    sizes[size],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={["flex flex-col gap-1.5", fullWidth ? "w-full" : "w-72", containerClassName].filter(Boolean).join(" ")}>
      {label && (
        <label htmlFor={selectId} className="text-sm font-medium text-blue-grey-100">
          {label}
          {required && <span className="ml-0.5 text-red-vivid-400">*</span>}
        </label>
      )}

      <div className="relative">
        <select
          id={selectId}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={message ? messageId : undefined}
          className={select}
          {...props}
        >
          {children}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-blue-grey-400" />
      </div>

      {message && (
        <p id={messageId} className={`text-sm ${error ? "text-red-vivid-300" : "text-blue-grey-400"}`}>
          {message}
        </p>
      )}
    </div>
  );
}

export function ChevronDownIcon(props: ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export default Select;
