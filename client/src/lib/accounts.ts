// Accounts from GET /api/me/accounts.
import { apiFetch } from "./api";

/** Amounts are whole dollars. For liabilities (cards, loans) `balance` is the amount owed, as a positive number. */
export interface BankAccount {
  account_id: string;
  type: string; // "checking" | "savings" | "credit_card" | "student_loan" | "auto_loan" | …
  name: string;
  is_liability: boolean;
  balance: number;
  credit_limit: number | null;
  apr_pct: number;
  apy_pct: number;
  monthly_payment: number;
}

export interface AccountsResponse {
  data: { as_of_date: string; stale: boolean; warnings: string[] };
  accounts: BankAccount[];
}

export const fetchAccounts = () => apiFetch<AccountsResponse>("/api/me/accounts");

/** Balance with sign: positive for money you have, negative for money owed. */
export const signedBalance = (a: BankAccount) => (a.is_liability ? -a.balance : a.balance);

export const isLoan = (a: BankAccount) => a.type.endsWith("_loan");

/** Spendable balance: deposit accounts minus credit card debt. Loans are excluded. */
export const currentBalance = (accounts: BankAccount[]) =>
  accounts.filter((a) => !isLoan(a)).reduce((sum, a) => sum + signedBalance(a), 0);
