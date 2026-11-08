import {
  getBills,
  getDeposits,
  getLoans,
  getMerchant,
  getPurchases,
  getTransfers,
  getWithdrawals,
  type Account,
} from "./nessie";

export type TransactionKind = "deposit" | "withdrawal" | "transfer" | "purchase" | "bill" | "loan";

export const transactionKinds: { kind: TransactionKind; label: string; plural: string }[] = [
  { kind: "deposit", label: "Deposit", plural: "Deposits" },
  { kind: "withdrawal", label: "Withdrawal", plural: "Withdrawals" },
  { kind: "transfer", label: "Transfer", plural: "Transfers" },
  { kind: "purchase", label: "Purchase", plural: "Purchases" },
  { kind: "bill", label: "Bill", plural: "Bills" },
  { kind: "loan", label: "Loan", plural: "Loans" },
];

/** One row in the transactions list, regardless of which Nessie resource it came from. */
export interface Transaction {
  id: string;
  kind: TransactionKind;
  title: string;
  /** Signed from the selected account's point of view: money in is positive. */
  amount: number;
  date: Date | null;
  /** Raw Nessie status, e.g. "pending", "executed", "recurring", "declined". */
  status: string;
}

// Nessie dates are "YYYY-MM-DD"; parse as local midnight so "today" lines up with the user's clock.
function parseDate(value?: string): Date | null {
  if (!value) return null;
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function accountLabel(account: Account) {
  const name = account.nickname?.trim() || account.type;
  const last4 = account.account_number?.slice(-4);
  return last4 ? `${name} ••${last4}` : name;
}

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// Merchant names are looked up once per id and shared across accounts.
const merchantNames = new Map<string, Promise<string | null>>();
function merchantName(id: string) {
  let name = merchantNames.get(id);
  if (!name) {
    name = getMerchant(id).then(
      (m) => m?.name ?? null,
      () => null,
    );
    merchantNames.set(id, name);
  }
  return name;
}

/** Fetches every transaction type for an account and merges them, newest first. */
export async function getAccountTransactions(account: Account, accounts: Account[]): Promise<Transaction[]> {
  const id = account._id;
  const results = await Promise.allSettled([
    getDeposits(id),
    getWithdrawals(id),
    getTransfers(id),
    getPurchases(id),
    getBills(id),
    getLoans(id),
  ]);

  // Surface an error only when nothing loaded; a single failing endpoint shouldn't blank the page.
  if (results.every((r) => r.status === "rejected")) throw (results[0] as PromiseRejectedResult).reason;
  const value = <T,>(r: PromiseSettledResult<T[]>) => (r.status === "fulfilled" && Array.isArray(r.value) ? r.value : []);
  const [deposits, withdrawals, transfers, purchases, bills, loans] = [
    value(results[0]),
    value(results[1]),
    value(results[2]),
    value(results[3]),
    value(results[4]),
    value(results[5]),
  ] as const;

  const nameOf = (accountId: string) => {
    const other = accounts.find((a) => a._id === accountId);
    return other ? accountLabel(other) : "another account";
  };

  const merchants = await Promise.all(purchases.map((p) => merchantName(p.merchant_id)));

  const rows: Transaction[] = [
    ...deposits.map((d) => ({
      id: d._id,
      kind: "deposit" as const,
      title: d.description || "Deposit",
      amount: d.amount,
      date: parseDate(d.transaction_date),
      status: d.status,
    })),
    ...withdrawals.map((w) => ({
      id: w._id,
      kind: "withdrawal" as const,
      title: w.description || "Withdrawal",
      amount: -w.amount,
      date: parseDate(w.transaction_date),
      status: w.status,
    })),
    ...transfers.map((t) => {
      const outgoing = t.payer_id === id;
      return {
        id: t._id,
        kind: "transfer" as const,
        title: t.description || (outgoing ? `To ${nameOf(t.payee_id)}` : `From ${nameOf(t.payer_id)}`),
        amount: outgoing ? -t.amount : t.amount,
        date: parseDate(t.transaction_date),
        status: t.status,
      };
    }),
    ...purchases.map((p, i) => ({
      id: p._id,
      kind: "purchase" as const,
      title: merchants[i] || p.description || "Purchase",
      amount: -p.amount,
      date: parseDate(p.purchase_date),
      status: p.status,
    })),
    ...bills.map((b) => ({
      id: b._id,
      kind: "bill" as const,
      title: b.nickname || b.payee || "Bill",
      amount: -b.payment_amount,
      date: parseDate(b.payment_date ?? b.upcoming_payment_date ?? b.creation_date),
      status: b.status,
    })),
    ...loans.map((l) => ({
      id: l._id,
      kind: "loan" as const,
      title: l.description || `${capitalize(l.type)} loan`,
      amount: l.amount,
      date: parseDate(l.creation_date),
      status: l.status,
    })),
  ];

  // Newest first; undated rows sink to the bottom.
  return rows.sort((a, b) => (b.date?.getTime() ?? -Infinity) - (a.date?.getTime() ?? -Infinity));
}
