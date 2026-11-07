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
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 " +
  "disabled:pointer-events-none disabled:opacity-50 cursor-pointer";

const variants: Record<Variant, string> = {
  primary:
    "bg-purple-600 text-white hover:bg-purple-700 active:bg-purple-800 focus-visible:ring-purple-400",
  secondary:
    "bg-teal-500 text-white hover:bg-teal-600 active:bg-teal-700 focus-visible:ring-teal-300",
  outline:
    "border border-blue-grey-300 bg-transparent text-blue-grey-800 hover:bg-blue-grey-050 active:bg-blue-grey-100 focus-visible:ring-blue-grey-300",
  ghost:
    "bg-transparent text-blue-grey-700 hover:bg-blue-grey-100 active:bg-blue-grey-200 focus-visible:ring-blue-grey-300",
  danger:
    "bg-red-vivid-600 text-white hover:bg-red-vivid-700 active:bg-red-vivid-800 focus-visible:ring-red-vivid-300",
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
