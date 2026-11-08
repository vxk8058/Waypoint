// Thin client for Capital One's Nessie API (http://api.nessieisreal.com/documentation).
// Configure with VITE_NESSIE_API_KEY and, optionally, VITE_NESSIE_CUSTOMER_ID in client/.env.local.
// Without a key, requests are served by an in-memory mock with filler data (see mock-nessie.ts).

import { mockRequest } from "./mock-nessie";

const BASE_URL = import.meta.env.VITE_NESSIE_BASE_URL ?? "http://api.nessieisreal.com";
const API_KEY: string | undefined = import.meta.env.VITE_NESSIE_API_KEY;
const CUSTOMER_ID: string | undefined = import.meta.env.VITE_NESSIE_CUSTOMER_ID;

/** True when talking to the real API; false when serving filler data. */
export const isNessieConfigured = Boolean(API_KEY);

export class NessieError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "NessieError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: { method?: "GET" | "POST"; body?: unknown }): Promise<T> {
  if (!API_KEY) {
    try {
      return await mockRequest<T>(init?.method ?? "GET", path, init?.body);
    } catch (err) {
      throw new NessieError(err instanceof Error ? err.message : String(err), (err as { status?: number }).status ?? 500);
    }
  }

  const url = new URL(path, BASE_URL);
  url.searchParams.set("key", API_KEY);

  const res = await fetch(url, {
    method: init?.method ?? "GET",
    headers: init?.body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
    body: init?.body ? JSON.stringify(init.body) : undefined,
  });

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // Nessie errors look like { code, message, culprit?: string[] }.
    const culprit = Array.isArray(data?.culprit) && data.culprit.length ? ` (${data.culprit.join(", ")})` : "";
    throw new NessieError(`${data?.message ?? res.statusText}${culprit}`, res.status);
  }
  // POSTs wrap the created object as { code, message, objectCreated }.
  return (init?.method === "POST" ? data?.objectCreated : data) as T;
}

// ---------- Types ----------

export type AccountType = "Credit Card" | "Savings" | "Checking";
export type Medium = "balance" | "rewards";
export type TransactionStatus = "pending" | "cancelled" | "completed" | "executed";

export interface Account {
  _id: string;
  type: AccountType;
  nickname: string;
  rewards: number;
  balance: number;
  account_number: string;
  customer_id: string;
}

export interface Deposit {
  _id: string;
  type: "deposit";
  transaction_date?: string;
  status: TransactionStatus;
  payee_id: string;
  medium: Medium;
  amount: number;
  description?: string;
}

export interface Withdrawal {
  _id: string;
  type: "withdrawal";
  transaction_date?: string;
  status: TransactionStatus;
  payer_id: string;
  medium: Medium;
  amount: number;
  description?: string;
}

export interface Transfer {
  _id: string;
  type: "p2p";
  transaction_date?: string;
  status: TransactionStatus;
  medium: Medium;
  payer_id: string;
  payee_id: string;
  amount: number;
  description?: string;
}

export interface Purchase {
  _id: string;
  type: "merchant";
  merchant_id: string;
  payer_id: string;
  purchase_date?: string;
  amount: number;
  status: TransactionStatus;
  medium: Medium;
  description?: string;
}

export type BillStatus = "pending" | "cancelled" | "completed" | "recurring";

export interface Bill {
  _id: string;
  status: BillStatus;
  payee: string;
  nickname?: string;
  creation_date?: string;
  payment_date?: string;
  recurring_date?: number;
  upcoming_payment_date?: string;
  payment_amount: number;
  account_id: string;
}

export type LoanType = "home" | "auto" | "small business";
export type LoanStatus = "pending" | "approved" | "declined";

export interface Loan {
  _id: string;
  type: LoanType;
  status: LoanStatus;
  credit_score: number;
  monthly_payment: number;
  amount: number;
  description?: string;
  creation_date?: string;
  account_id: string;
}

export interface Merchant {
  _id: string;
  name: string;
  category?: string[];
}

// ---------- Accounts & merchants ----------

export function getAccounts() {
  return request<Account[]>(CUSTOMER_ID ? `/customers/${CUSTOMER_ID}/accounts` : "/accounts");
}

export function getMerchants() {
  return request<Merchant[]>("/merchants");
}

export function getMerchant(id: string) {
  return request<Merchant>(`/merchants/${id}`);
}

// ---------- Transactions (list) ----------

export const getDeposits = (accountId: string) => request<Deposit[]>(`/accounts/${accountId}/deposits`);
export const getWithdrawals = (accountId: string) => request<Withdrawal[]>(`/accounts/${accountId}/withdrawals`);
// Without a `type` filter Nessie returns transfers where the account is either payer or payee.
export const getTransfers = (accountId: string) => request<Transfer[]>(`/accounts/${accountId}/transfers`);
export const getPurchases = (accountId: string) => request<Purchase[]>(`/accounts/${accountId}/purchases`);
export const getBills = (accountId: string) => request<Bill[]>(`/accounts/${accountId}/bills`);
export const getLoans = (accountId: string) => request<Loan[]>(`/accounts/${accountId}/loans`);

// ---------- Transactions (create) ----------

interface MoneyMovementInput {
  amount: number;
  description?: string;
  transaction_date?: string;
  medium?: Medium;
}

export function createDeposit(accountId: string, input: MoneyMovementInput) {
  return request<Deposit>(`/accounts/${accountId}/deposits`, { method: "POST", body: { medium: "balance", ...input } });
}

export function createWithdrawal(accountId: string, input: MoneyMovementInput) {
  return request<Withdrawal>(`/accounts/${accountId}/withdrawals`, { method: "POST", body: { medium: "balance", ...input } });
}

export function createTransfer(accountId: string, input: MoneyMovementInput & { payee_id: string }) {
  return request<Transfer>(`/accounts/${accountId}/transfers`, { method: "POST", body: { medium: "balance", ...input } });
}

export function createPurchase(
  accountId: string,
  input: { merchant_id: string; amount: number; description?: string; purchase_date?: string; medium?: Medium },
) {
  return request<Purchase>(`/accounts/${accountId}/purchases`, { method: "POST", body: { medium: "balance", ...input } });
}

export function createBill(
  accountId: string,
  input: { payee: string; payment_amount: number; nickname?: string; payment_date?: string; recurring_date?: number; status?: BillStatus },
) {
  return request<Bill>(`/accounts/${accountId}/bills`, { method: "POST", body: { status: "pending", ...input } });
}

export function createLoan(
  accountId: string,
  input: { type: LoanType; amount: number; monthly_payment: number; credit_score: number; description?: string; status?: LoanStatus },
) {
  return request<Loan>(`/accounts/${accountId}/loans`, { method: "POST", body: { status: "pending", ...input } });
}
