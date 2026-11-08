// Recurring bills from GET /api/me/bills.
import { apiFetch } from "./api";

/** Amounts are whole dollars; dates are "YYYY-MM-DD". */
export interface Bill {
  bill_key: string;
  payee: string;
  nickname: string;
  category: string; // "housing" | "utilities" | "phone" | "subscriptions" | "insurance" | …
  amount: number;
  day_of_month: number;
  next_due_date: string;
  account_id: string;
  status: string; // "recurring" | "pending" | …
}

export interface BillsResponse {
  data: { as_of_date: string; stale: boolean; warnings: string[] };
  /** Soonest due first. */
  bills: Bill[];
  /** Sum of active (recurring + pending) bills: what comes out each month. */
  monthly_total: number;
}

export const fetchBills = () => apiFetch<BillsResponse>("/api/me/bills");

/** Parse "YYYY-MM-DD" as a local date (new Date("YYYY-MM-DD") would be UTC midnight and can show the previous day). */
export function parseDate(value: string) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}
