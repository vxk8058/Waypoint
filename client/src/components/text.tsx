import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";

type Variant =
  | "display"
  | "h1"
  | "h2"
  | "h3"
  | "h4"
  | "lead"
  | "body"
  | "small"
  | "caption"
  | "label"
  | "overline";

type Tone = "default" | "muted" | "subtle" | "primary" | "accent" | "danger" | "warning" | "inverse";
type Weight = "light" | "normal" | "medium" | "semibold" | "bold";
type Align = "left" | "center" | "right";

const variants: Record<Variant, string> = {
  display: "text-5xl sm:text-6xl font-bold tracking-tight leading-none",
  h1: "text-4xl font-bold tracking-tight leading-tight",
  h2: "text-3xl font-semibold tracking-tight leading-tight",
  h3: "text-2xl font-semibold leading-snug",
  h4: "text-xl font-semibold leading-snug",
  lead: "text-lg leading-relaxed",
  body: "text-base leading-relaxed",
  small: "text-sm leading-normal",
  caption: "text-xs leading-normal",
  label: "text-sm font-medium leading-none",
  overline: "text-xs font-semibold uppercase tracking-widest",
};

// The HTML element each variant renders by default (override with `as`).
const defaultElements: Record<Variant, ElementType> = {
  display: "h1",
  h1: "h1",
  h2: "h2",
  h3: "h3",
  h4: "h4",
  lead: "p",
  body: "p",
  small: "p",
  caption: "span",
  label: "span",
  overline: "span",
};

// Variants that default to a lighter colour when no tone is given.
const defaultTones: Partial<Record<Variant, Tone>> = {
  lead: "muted",
  caption: "subtle",
  overline: "primary",
};

const tones: Record<Tone, string> = {
  default: "text-blue-grey-050",
  muted: "text-blue-grey-300",
  subtle: "text-blue-grey-500",
  primary: "text-purple-300",
  accent: "text-teal-300",
  danger: "text-red-vivid-300",
  warning: "text-yellow-vivid-300",
  inverse: "text-blue-grey-900",
};

const weights: Record<Weight, string> = {
  light: "font-light",
  normal: "font-normal",
  medium: "font-medium",
  semibold: "font-semibold",
  bold: "font-bold",
};

const aligns: Record<Align, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

type OwnProps<T extends ElementType> = {
  as?: T;
  variant?: Variant;
  tone?: Tone;
  weight?: Weight;
  align?: Align;
  truncate?: boolean;
  className?: string;
  children?: ReactNode;
};

export type TextProps<T extends ElementType = "p"> = OwnProps<T> &
  Omit<ComponentPropsWithoutRef<T>, keyof OwnProps<T>>;

export function Text<T extends ElementType = "p">({
  as,
  variant = "body",
  tone,
  weight,
  align,
  truncate = false,
  className = "",
  ...props
}: TextProps<T>) {
  const Component: ElementType = as ?? defaultElements[variant];

  const classes = [
    variants[variant],
    tones[tone ?? defaultTones[variant] ?? "default"],
    weight && weights[weight],
    align && aligns[align],
    truncate && "truncate",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <Component className={classes} {...props} />;
}

export default Text;
