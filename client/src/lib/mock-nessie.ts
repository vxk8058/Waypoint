// In-memory stand-in for the Nessie API, used when no VITE_NESSIE_API_KEY is set.
// It answers the same paths with the same shapes, so the app can't tell the difference.
// Data resets on page reload.

import type { Account, Bill, Deposit, Loan, Merchant, Purchase, Transfer, Withdrawal } from "./nessie";

function daysAgo(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

let nextId = 1000;
const newId = () => `mock-${nextId++}`;

const CUSTOMER = "mock-customer";

// Same accounts as the home page placeholders.
const accounts: Account[] = [
  { _id: "chk-7127", type: "Checking", nickname: "Checking", rewards: 0, balance: 3215.47, account_number: "4400128855127127", customer_id: CUSTOMER },
  { _id: "sav-8823", type: "Savings", nickname: "Savings", rewards: 0, balance: 8940.12, account_number: "4400128855128823", customer_id: CUSTOMER },
  { _id: "sav-5679", type: "Savings", nickname: "Emergency fund", rewards: 0, balance: 1500.0, account_number: "4400128855125679", customer_id: CUSTOMER },
  { _id: "cc-2502", type: "Credit Card", nickname: "Credit card", rewards: 1240, balance: -1175.27, account_number: "4400128855122502", customer_id: CUSTOMER },
];

const merchants: Merchant[] = [
  { _id: "m-blue-bottle", name: "Blue Bottle Coffee", category: ["food"] },
  { _id: "m-whole-foods", name: "Whole Foods Market", category: ["groceries"] },
  { _id: "m-trader-joes", name: "Trader Joe's", category: ["groceries"] },
  { _id: "m-target", name: "Target", category: ["shopping"] },
  { _id: "m-shell", name: "Shell", category: ["gas"] },
  { _id: "m-chipotle", name: "Chipotle", category: ["food"] },
  { _id: "m-amazon", name: "Amazon", category: ["shopping"] },
  { _id: "m-cvs", name: "CVS Pharmacy", category: ["health"] },
  { _id: "m-amc", name: "AMC Theatres", category: ["entertainment"] },
  { _id: "m-uber", name: "Uber", category: ["transport"] },
  { _id: "m-spotify", name: "Spotify", category: ["subscriptions"] },
];

const deposits: Deposit[] = [
  { _id: newId(), type: "deposit", transaction_date: daysAgo(0), status: "pending", payee_id: "chk-7127", medium: "balance", amount: 2150.0, description: "Payroll · Acme Corp" },
  { _id: newId(), type: "deposit", transaction_date: daysAgo(14), status: "executed", payee_id: "chk-7127", medium: "balance", amount: 2150.0, description: "Payroll · Acme Corp" },
  { _id: newId(), type: "deposit", transaction_date: daysAgo(9), status: "executed", payee_id: "chk-7127", medium: "balance", amount: 40.0, description: "Venmo from Sam Lee" },
  { _id: newId(), type: "deposit", transaction_date: daysAgo(28), status: "executed", payee_id: "chk-7127", medium: "balance", amount: 2150.0, description: "Payroll · Acme Corp" },
  { _id: newId(), type: "deposit", transaction_date: daysAgo(30), status: "executed", payee_id: "sav-8823", medium: "balance", amount: 12.84, description: "Interest" },
  { _id: newId(), type: "deposit", transaction_date: daysAgo(6), status: "executed", payee_id: "sav-5679", medium: "balance", amount: 100.0, description: "Birthday cash" },
];

const withdrawals: Withdrawal[] = [
  { _id: newId(), type: "withdrawal", transaction_date: daysAgo(3), status: "executed", payer_id: "chk-7127", medium: "balance", amount: 60.0, description: "ATM · 5th & Main" },
  { _id: newId(), type: "withdrawal", transaction_date: daysAgo(17), status: "executed", payer_id: "chk-7127", medium: "balance", amount: 100.0, description: "ATM · Campus Center" },
  { _id: newId(), type: "withdrawal", transaction_date: daysAgo(22), status: "cancelled", payer_id: "sav-8823", medium: "balance", amount: 250.0, description: "Branch withdrawal" },
];

const transfers: Transfer[] = [
  { _id: newId(), type: "p2p", transaction_date: daysAgo(1), status: "executed", medium: "balance", payer_id: "chk-7127", payee_id: "sav-8823", amount: 300.0 },
  { _id: newId(), type: "p2p", transaction_date: daysAgo(15), status: "executed", medium: "balance", payer_id: "chk-7127", payee_id: "sav-8823", amount: 300.0 },
  { _id: newId(), type: "p2p", transaction_date: daysAgo(8), status: "executed", medium: "balance", payer_id: "chk-7127", payee_id: "cc-2502", amount: 450.0, description: "Credit card payment" },
  { _id: newId(), type: "p2p", transaction_date: daysAgo(20), status: "executed", medium: "balance", payer_id: "sav-8823", payee_id: "sav-5679", amount: 200.0 },
];

const purchase = (days: number, merchant_id: string, amount: number, payer_id = "chk-7127", status: Purchase["status"] = "executed"): Purchase => ({
  _id: newId(),
  type: "merchant",
  merchant_id,
  payer_id,
  purchase_date: daysAgo(days),
  amount,
  status,
  medium: "balance",
});

const purchases: Purchase[] = [
  purchase(0, "m-blue-bottle", 6.75, "chk-7127", "pending"),
  purchase(0, "m-cvs", 11.8, "chk-7127", "pending"),
  purchase(1, "m-chipotle", 13.45),
  purchase(2, "m-trader-joes", 64.21),
  purchase(4, "m-shell", 48.9),
  purchase(5, "m-uber", 18.32),
  purchase(7, "m-blue-bottle", 5.5),
  purchase(10, "m-whole-foods", 92.17),
  purchase(12, "m-target", 37.64),
  purchase(0, "m-amazon", 42.99, "cc-2502", "pending"),
  purchase(2, "m-amc", 31.5, "cc-2502"),
  purchase(6, "m-spotify", 11.99, "cc-2502"),
  purchase(11, "m-amazon", 129.0, "cc-2502"),
  purchase(19, "m-target", 58.12, "cc-2502"),
];

const bills: Bill[] = [
  { _id: newId(), status: "recurring", payee: "Parkside Apartments", nickname: "Rent", creation_date: daysAgo(90), upcoming_payment_date: daysAgo(-3), recurring_date: 1, payment_amount: 1450.0, account_id: "chk-7127" },
  { _id: newId(), status: "recurring", payee: "Verizon", nickname: "Phone bill", creation_date: daysAgo(90), upcoming_payment_date: daysAgo(-9), recurring_date: 15, payment_amount: 65.0, account_id: "chk-7127" },
  { _id: newId(), status: "completed", payee: "Comcast", nickname: "Internet", creation_date: daysAgo(60), payment_date: daysAgo(18), payment_amount: 59.99, account_id: "chk-7127" },
  { _id: newId(), status: "completed", payee: "PG&E", nickname: "Electricity", creation_date: daysAgo(40), payment_date: daysAgo(13), payment_amount: 84.36, account_id: "chk-7127" },
  { _id: newId(), status: "pending", payee: "Planet Fitness", nickname: "Gym membership", creation_date: daysAgo(30), payment_date: daysAgo(-15), payment_amount: 40.0, account_id: "cc-2502" },
];

const loans: Loan[] = [
  { _id: newId(), type: "auto", status: "approved", credit_score: 712, monthly_payment: 312.5, amount: 14500, description: "Car loan · 2021 Civic", creation_date: daysAgo(45), account_id: "chk-7127" },
  { _id: newId(), type: "small business", status: "pending", credit_score: 712, monthly_payment: 180.0, amount: 8000, description: "Small business loan", creation_date: daysAgo(4), account_id: "sav-8823" },
  { _id: newId(), type: "home", status: "declined", credit_score: 690, monthly_payment: 1900.0, amount: 320000, description: "Mortgage pre-approval", creation_date: daysAgo(26), account_id: "sav-8823" },
];

// ---------- Request router ----------

class MockError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const findAccount = (id: string) => {
  const account = accounts.find((a) => a._id === id);
  if (!account) throw new MockError("Account not found", 404);
  return account;
};

const today = () => daysAgo(0);
const clone = <T,>(value: T): T => structuredClone(value);
// A little latency so loading states are visible, as with the real API.
const delay = () => new Promise((resolve) => setTimeout(resolve, 250));

// Body shapes come from the typed create* helpers in nessie.ts.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = any;

function handle(method: "GET" | "POST", path: string, body: Body): unknown {
  if (path === "/accounts" || path === `/customers/${CUSTOMER}/accounts` || /^\/customers\/[^/]+\/accounts$/.test(path)) return accounts;
  if (path === "/merchants") return merchants;

  const merchant = path.match(/^\/merchants\/([^/]+)$/);
  if (merchant) {
    const found = merchants.find((m) => m._id === merchant[1]);
    if (!found) throw new MockError("Merchant not found", 404);
    return found;
  }

  const match = path.match(/^\/accounts\/([^/]+)\/(deposits|withdrawals|transfers|purchases|bills|loans)$/);
  if (!match) throw new MockError(`No mock route for ${method} ${path}`, 404);
  const [, accountId, resource] = match;
  const account = findAccount(accountId);

  if (method === "GET") {
    switch (resource) {
      case "deposits": return deposits.filter((d) => d.payee_id === accountId);
      case "withdrawals": return withdrawals.filter((w) => w.payer_id === accountId);
      case "transfers": return transfers.filter((t) => t.payer_id === accountId || t.payee_id === accountId);
      case "purchases": return purchases.filter((p) => p.payer_id === accountId);
      case "bills": return bills.filter((b) => b.account_id === accountId);
      case "loans": return loans.filter((l) => l.account_id === accountId);
    }
  }

  // POST: create the record and, for money movements, settle it immediately.
  switch (resource) {
    case "deposits": {
      const created: Deposit = { _id: newId(), type: "deposit", status: "executed", payee_id: accountId, transaction_date: today(), ...body };
      deposits.push(created);
      account.balance += created.amount;
      return created;
    }
    case "withdrawals": {
      const created: Withdrawal = { _id: newId(), type: "withdrawal", status: "executed", payer_id: accountId, transaction_date: today(), ...body };
      withdrawals.push(created);
      account.balance -= created.amount;
      return created;
    }
    case "transfers": {
      const payee = findAccount(body.payee_id);
      const created: Transfer = { _id: newId(), type: "p2p", status: "executed", payer_id: accountId, transaction_date: today(), ...body };
      transfers.push(created);
      account.balance -= created.amount;
      payee.balance += created.amount;
      return created;
    }
    case "purchases": {
      const created: Purchase = { _id: newId(), type: "merchant", status: "executed", payer_id: accountId, purchase_date: today(), ...body };
      purchases.push(created);
      account.balance -= created.amount;
      return created;
    }
    case "bills": {
      const created: Bill = { _id: newId(), account_id: accountId, creation_date: today(), ...body };
      bills.push(created);
      return created;
    }
    case "loans": {
      if (account.type === "Credit Card") throw new MockError("Loans can't be opened on a credit card account", 400);
      const created: Loan = { _id: newId(), account_id: accountId, creation_date: today(), ...body };
      loans.push(created);
      return created;
    }
  }
  throw new MockError(`No mock route for ${method} ${path}`, 404);
}

export async function mockRequest<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  await delay();
  // Round balances so repeated float math doesn't drift into 0.30000000000000004.
  const result = handle(method, path, body);
  for (const a of accounts) a.balance = Math.round(a.balance * 100) / 100;
  return clone(result) as T;
}

export { MockError };
