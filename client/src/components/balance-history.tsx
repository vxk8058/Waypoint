import { useMemo, useState } from "react";
import type { BankAccount } from "../lib/accounts";
import { buildBalanceHistory, fetchAllTransactions } from "../lib/balance-history";
import { useAsync } from "../lib/use-async";
import { LineChart } from "./charts";

const RANGES = [
  { key: "1M", label: "1M", months: 1 },
  { key: "3M", label: "3M", months: 3 },
  { key: "6M", label: "6M", months: 6 },
  { key: "all", label: "All", months: Infinity },
] as const;
type RangeKey = (typeof RANGES)[number]["key"];

const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0, signDisplay: "always" });

/** First day shown for a range ending at `asOf` ("YYYY-MM-DD"). */
function rangeStart(asOf: string, months: number): string {
  if (!Number.isFinite(months)) return "";
  const d = new Date(`${asOf}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

export interface BalanceHistoryProps {
  accounts: BankAccount[];
  /** Date the balances are from (the API's data.as_of_date). */
  asOf: string;
  className?: string;
}

/** Line chart of the current balance's daily history. */
export function BalanceHistory({ accounts, asOf, className = "" }: BalanceHistoryProps) {
  const [range, setRange] = useState<RangeKey>("6M");
  const { data: transactions, error, loading } = useAsync(fetchAllTransactions, []);

  const history = useMemo(
    () => (transactions ? buildBalanceHistory(accounts, transactions, asOf) : []),
    [accounts, transactions, asOf],
  );

  const months = RANGES.find((r) => r.key === range)!.months;
  const start = rangeStart(asOf, months);
  const points = history.filter((p) => p.date >= start);
  const change = points.length > 1 ? points[points.length - 1].balance - points[0].balance : undefined;
  const period = range === "all" && points.length
    ? `since ${shortDate.format(new Date(`${points[0].date}T00:00:00Z`))}`
    : months === 1 ? "over the last month" : `over the last ${months} months`;

  const spec = {
    title: "Balance history",
    subtitle: error
      ? `Couldn't load transactions: ${error.message}`
      : change !== undefined
        ? `${dollars.format(change)} ${period}`
        : undefined,
    x: points.map((p) => p.date),
    xType: "time" as const,
    series: [{ name: "Balance", values: points.map((p) => p.balance) }],
    area: true,
    markers: "last" as const,
    valueLabels: "last" as const,
    valueFormat: { style: "currency" as const },
    legend: { show: false },
    height: 220,
    emptyMessage: error ? "No data" : "No transactions yet",
  };

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div role="group" aria-label="Time range" className="flex gap-1 self-end rounded-lg border border-blue-grey-800 p-0.5">
        {RANGES.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => setRange(r.key)}
            aria-pressed={range === r.key}
            className={[
              "cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-purple-400",
              range === r.key ? "bg-surface-raised text-blue-grey-050" : "text-blue-grey-300 hover:text-blue-grey-050",
            ].join(" ")}
          >
            {r.label}
          </button>
        ))}
      </div>
      <LineChart spec={spec} loading={loading && !transactions} />
    </div>
  );
}
