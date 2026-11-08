const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export interface MoneyProps {
  amount: number;
  /** Prefix with an explicit "+" or "−", e.g. for money in/out of an account. */
  signed?: boolean;
}

// Renders "$1,020.00" with the cents raised and smaller, e.g. $1,020⁰⁰.
export function Money({ amount, signed = false }: MoneyProps) {
  const formatted = currency.format(signed ? Math.abs(amount) : amount);
  const dot = formatted.lastIndexOf(".");
  const sign = signed ? (amount < 0 ? "−" : "+") : "";
  return (
    <span className="tabular-nums">
      {sign}
      {formatted.slice(0, dot)}
      <sup className="ml-px text-[0.65em] font-medium">{formatted.slice(dot)}</sup>
    </span>
  );
}

export default Money;
