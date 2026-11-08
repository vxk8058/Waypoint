import { fetchAllTransactions } from "../lib/transactions";
import { useAsync } from "../lib/use-async";

interface Account {
  type: string;
  balance: number;
}

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const monthName = (ym: string) =>
  new Date(`${ym}-01T00:00:00Z`).toLocaleString("en-US", { month: "short", timeZone: "UTC" });

function previousMonth(ym: string) {
  const [y, m] = ym.split("-").map(Number);
  return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
}

const SIZE = 300;
const C = SIZE / 2;
const R = 92;
const point = (i: number, frac: number) => {
  const angle = (-90 + i * 90) * (Math.PI / 180); // Savings top, then clockwise
  return [C + R * frac * Math.cos(angle), C + R * frac * Math.sin(angle)];
};
const polygon = (fracs: number[]) => fracs.map((f, i) => point(i, f).join(",")).join(" ");

/**
 * This month vs last month on four spokes. Units differ (dollars vs a count), so each spoke is scaled
 * to the larger of its two values and the real numbers are printed; the shapes compare months, not spokes.
 */
export function StatsRadar({ accounts, asOf, className = "" }: { accounts: Account[]; asOf: string; className?: string }) {
  const { data: txns } = useAsync(() => fetchAllTransactions(), []);
  if (!txns) return <div aria-hidden="true" className={`h-80 animate-pulse rounded-lg bg-surface ${className}`} />;

  const month = asOf.slice(0, 7);
  const prev = previousMonth(month);
  const now = (type: string) => accounts.filter((a) => a.type === type).reduce((sum, a) => sum + a.balance, 0);
  // Last month-end balance = today's balance minus this month's changes.
  const before = (type: string) =>
    now(type) - txns.filter((t) => t.account_type === type && t.date >= `${month}-01`).reduce((s, t) => s + t.balance_change, 0);
  const count = (ym: string) => txns.filter((t) => t.date.startsWith(ym)).length;
  const spokes = [
    { label: "Savings", now: now("savings"), prev: before("savings"), money: true },
    { label: "Checking", now: now("checking"), prev: before("checking"), money: true },
    { label: "Credit owed", now: now("credit_card"), prev: before("credit_card"), money: true },
    { label: "Transactions", now: count(month), prev: count(prev), money: false },
  ];
  const frac = (value: number, s: (typeof spokes)[number]) => (Math.max(s.now, s.prev) > 0 ? Math.max(0, value) / Math.max(s.now, s.prev) : 0);
  const show = (value: number, money: boolean) => (money ? dollars.format(value) : String(value));
  const anchors = ["middle", "start", "middle", "end"] as const;
  const [thisName, lastName] = [monthName(month), monthName(prev)];

  return (
    <section aria-labelledby="radar-heading" className={`flex w-full flex-col gap-2 rounded-lg border border-blue-grey-700 px-4 py-4 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="radar-heading" className="text-xl font-semibold">Your money at a glance</h2>
        <p className="flex gap-3 text-xs text-blue-grey-300">
          <span><span aria-hidden="true" className="mr-1 inline-block size-2 rounded-full bg-purple-400" />{thisName}</span>
          <span><span aria-hidden="true" className="mr-1 inline-block size-2 rounded-full bg-teal-400" />{lastName}</span>
        </p>
      </div>

      {/* Side padding so the left and right labels aren't clipped. */}
      <svg viewBox={`-70 0 ${SIZE + 140} ${SIZE}`} role="img" aria-label={`Radar comparing ${thisName} with ${lastName}`} className="mx-auto w-full max-w-sm">
        {[0.25, 0.5, 0.75, 1].map((ring) => (
          <polygon key={ring} points={polygon([ring, ring, ring, ring])} fill="none" stroke="var(--color-blue-grey-800)" />
        ))}
        {spokes.map((_, i) => {
          const [x, y] = point(i, 1);
          return <line key={i} x1={C} y1={C} x2={x} y2={y} stroke="var(--color-blue-grey-800)" />;
        })}
        <polygon points={polygon(spokes.map((s) => frac(s.prev, s)))} fill="var(--color-teal-400)" fillOpacity={0.2} stroke="var(--color-teal-400)" strokeWidth={1.5} />
        <polygon points={polygon(spokes.map((s) => frac(s.now, s)))} fill="var(--color-purple-400)" fillOpacity={0.3} stroke="var(--color-purple-400)" strokeWidth={2} />
        {spokes.map((s, i) => {
          const [x, y] = point(i, 1.22);
          return (
            <text key={s.label} x={x} y={y + (i === 2 ? 6 : i === 0 ? -6 : 0)} textAnchor={anchors[i]} className="fill-blue-grey-100 text-[11px] font-semibold">
              {s.label}
              <tspan x={x} dy="13" className="fill-blue-grey-400 font-normal">
                {show(s.now, s.money)} · {show(s.prev, s.money)}
              </tspan>
            </text>
          );
        })}
      </svg>

      <table className="sr-only">
        <caption>{thisName} compared with {lastName}</caption>
        <thead><tr><th>Measure</th><th>{thisName}</th><th>{lastName}</th></tr></thead>
        <tbody>
          {spokes.map((s) => (
            <tr key={s.label}><td>{s.label}</td><td>{show(s.now, s.money)}</td><td>{show(s.prev, s.money)}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-blue-grey-500">Each spoke is scaled to its own larger month; lower credit owed is better.</p>
    </section>
  );
}

export default StatsRadar;
