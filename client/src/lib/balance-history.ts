// Daily balance history, rebuilt backwards from current balances and transactions
// (the API has no statements). Uses the same definition as the Home page's current balance:
// checking + savings − credit card debt, loans excluded. Month-ends match the backend's
// monthly summary (closing_liquid minus card balances).
import { isLoan, signedBalance, type BankAccount } from "./accounts";
import type { ApiTransaction } from "./transactions";

export interface BalancePoint {
  date: string; // YYYY-MM-DD
  balance: number; // end-of-day balance
}

const DAY_MS = 86_400_000;
const isoDay = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const dayMs = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

/** One point per day, from the earliest transaction through `asOf`. */
export function buildBalanceHistory(accounts: BankAccount[], transactions: ApiTransaction[], asOf: string): BalancePoint[] {
  const tracked = new Map(accounts.filter((a) => !isLoan(a)).map((a) => [a.account_id, a]));
  let balance = [...tracked.values()].reduce((sum, a) => sum + signedBalance(a), 0);

  // Net signed change per day across tracked accounts.
  const changeByDay = new Map<string, number>();
  let first = asOf;
  for (const t of transactions) {
    const account = tracked.get(t.account_id);
    if (!account || t.date > asOf) continue;
    const change = account.is_liability ? -t.balance_change : t.balance_change;
    changeByDay.set(t.date, (changeByDay.get(t.date) ?? 0) + change);
    if (t.date < first) first = t.date;
  }

  // Walk back from asOf: a day's end balance, then undo that day's changes to get the previous day's.
  const points: BalancePoint[] = [];
  for (let ms = dayMs(asOf); ms >= dayMs(first); ms -= DAY_MS) {
    const day = isoDay(ms);
    points.push({ date: day, balance });
    balance -= changeByDay.get(day) ?? 0;
  }
  return points.reverse();
}
