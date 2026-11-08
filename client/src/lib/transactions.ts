// Transactions from GET /api/me/transactions.
import { apiFetch } from "./api";

/** Amounts are whole dollars; dates are "YYYY-MM-DD". */
export interface ApiTransaction {
  transaction_id: string;
  account_id: string;
  account_type: string;
  date: string;
  type: string; // "purchase" | "paycheck" | "deposit" | "payment" | "transfer_in" | "transfer_out" | "withdrawal" | "interest_accrual"
  category: string; // "groceries" | "payroll" | "housing" | "credit_card_payment" | …
  description: string;
  /** Always positive; `direction` says which way the money moved. */
  amount: number;
  direction: "in" | "out";
  /** Change to the account's balance; for liabilities, positive means more is owed. */
  balance_change: number;
  flow_class: string; // "income" | "expense" | "internal_transfer" | "non_cash"
  merchant_name: string | null;
  bill_key: string | null;
  nessie_resource: string | null; // "deposit" | "withdrawal" | "purchase" | "transfer" | null (e.g. interest)
}

interface TransactionsPage {
  items: ApiTransaction[];
  total: number;
}

const PAGE_SIZE = 500; // backend maximum

/** All of the user's transactions, newest first, optionally for one account (the endpoint pages at 500). */
export async function fetchAllTransactions(accountId?: string): Promise<ApiTransaction[]> {
  const all: ApiTransaction[] = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (accountId) params.set("account_id", accountId);
    const page = await apiFetch<TransactionsPage>(`/api/me/transactions?${params}`);
    all.push(...page.items);
    if (page.items.length === 0 || all.length >= page.total) return all;
  }
}

// ---------- list rows ----------

export type TransactionKind = "deposit" | "withdrawal" | "transfer" | "purchase" | "bill" | "interest";

export const transactionKinds: { kind: TransactionKind; label: string; plural: string }[] = [
  { kind: "purchase", label: "Purchase", plural: "Purchases" },
  { kind: "bill", label: "Bill", plural: "Bills" },
  { kind: "deposit", label: "Deposit", plural: "Deposits" },
  { kind: "transfer", label: "Transfer", plural: "Transfers" },
  { kind: "withdrawal", label: "Withdrawal", plural: "Withdrawals" },
  { kind: "interest", label: "Interest", plural: "Interest" },
];

/** One row in the transactions list. */
export interface Transaction {
  id: string;
  kind: TransactionKind;
  title: string;
  category: string;
  /** Signed from the account holder's point of view: money in (or debt paid down) is positive. */
  amount: number;
  date: Date;
}

function kindOf(t: ApiTransaction): TransactionKind {
  if (t.bill_key) return "bill";
  if (t.type === "interest_accrual") return "interest";
  switch (t.nessie_resource) {
    case "deposit":
    case "withdrawal":
    case "purchase":
      return t.nessie_resource;
    default:
      return "transfer"; // transfers, card payments, loan payments
  }
}

// "YYYY-MM-DD" as local midnight so "today" lines up with the user's clock.
function parseDate(value: string) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "credit_card_payment" → "Credit card payment" */
export const humanize = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1).replaceAll("_", " ") : s);

export function toTransaction(t: ApiTransaction): Transaction {
  return {
    id: t.transaction_id,
    kind: kindOf(t),
    title: t.merchant_name || t.description || humanize(t.type),
    category: humanize(t.category),
    amount: t.direction === "in" ? t.amount : -t.amount,
    date: parseDate(t.date),
  };
}

/** One account's transactions as list rows, newest first. */
export const getAccountTransactions = async (accountId: string) => (await fetchAllTransactions(accountId)).map(toTransaction);
