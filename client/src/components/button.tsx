import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas " +
  "disabled:pointer-events-none disabled:opacity-50 cursor-pointer";

const variants: Record<Variant, string> = {
  primary:
    "bg-purple-500 text-white hover:bg-purple-400 active:bg-purple-600 focus-visible:ring-purple-300",
  secondary:
    "bg-teal-400 text-blue-grey-900 hover:bg-teal-300 active:bg-teal-500 focus-visible:ring-teal-200",
  outline:
    "border border-blue-grey-600 bg-transparent text-blue-grey-100 hover:bg-surface-raised active:bg-blue-grey-800 focus-visible:ring-blue-grey-400",
  ghost:
    "bg-transparent text-blue-grey-200 hover:bg-surface-raised active:bg-blue-grey-800 focus-visible:ring-blue-grey-400",
  danger:
    "bg-red-vivid-600 text-white hover:bg-red-vivid-500 active:bg-red-vivid-700 focus-visible:ring-red-vivid-300",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-base",
  lg: "h-12 px-6 text-lg",
};

export function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  type = "button",
  className = "",
  ...props
}: ButtonProps) {
  const classes = [base, variants[variant], sizes[size], fullWidth && "w-full", className]
    .filter(Boolean)
    .join(" ");

  return <button type={type} className={classes} {...props} />;
}

export default Button;
