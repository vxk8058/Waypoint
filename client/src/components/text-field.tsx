import { useId } from "react";
import type { ComponentProps, ReactNode } from "react";

type Size = "sm" | "md" | "lg";

export interface TextFieldProps extends Omit<ComponentProps<"input">, "size"> {
  label?: string;
  hint?: string;
  error?: string;
  size?: Size;
  leading?: ReactNode;
  trailing?: ReactNode;
  fullWidth?: boolean;
  containerClassName?: string;
}

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-3 text-base",
  lg: "h-12 px-4 text-lg",
};

export function TextField({
  label,
  hint,
  error,
  size = "md",
  leading,
  trailing,
  fullWidth = false,
  id,
  type = "text",
  disabled,
  required,
  className = "",
  containerClassName = "",
  ...props
}: TextFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const messageId = `${inputId}-message`;
  const message = error ?? hint;

  const wrapper = [
    "flex items-center gap-2 rounded-lg border bg-canvas transition-colors",
    "focus-within:ring-2 focus-within:ring-offset-1 focus-within:ring-offset-canvas",
    error
      ? "border-red-vivid-400 focus-within:ring-red-vivid-400/50"
      : "border-blue-grey-600 hover:border-blue-grey-500 focus-within:border-purple-400 focus-within:ring-purple-400/40",
    disabled && "cursor-not-allowed bg-surface opacity-60",
    sizes[size],
  ]
    .filter(Boolean)
    .join(" ");

  const input = [
    "min-w-0 flex-1 bg-transparent text-blue-grey-050 outline-none placeholder:text-blue-grey-500",
    "disabled:cursor-not-allowed",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={["flex flex-col gap-1.5", fullWidth ? "w-full" : "w-72", containerClassName]
        .filter(Boolean)
        .join(" ")}
    >
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-blue-grey-100">
          {label}
          {required && <span className="ml-0.5 text-red-vivid-400">*</span>}
        </label>
      )}

      <div className={wrapper}>
        {leading && <span className="flex shrink-0 text-blue-grey-400">{leading}</span>}
        <input
          id={inputId}
          type={type}
          disabled={disabled}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={message ? messageId : undefined}
          className={input}
          {...props}
        />
        {trailing && <span className="flex shrink-0 text-blue-grey-400">{trailing}</span>}
      </div>

      {message && (
        <p
          id={messageId}
          className={`text-sm ${error ? "text-red-vivid-300" : "text-blue-grey-400"}`}
        >
          {message}
        </p>
      )}
    </div>
  );
}

export default TextField;
