import type { SVGProps } from "react";
import { Money } from "../components/money";
import { Text } from "../components/text";
import { getSessionUser } from "../lib/api";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

interface Account {
  id: string;
  type: string;
  last4: string;
  balance: number;
}

// Placeholder until accounts come from the API. Credit balances owed are negative.
const accounts: Account[] = [
  { id: "chk-7127", type: "Checking", last4: "7127", balance: 3215.47 },
  { id: "sav-8823", type: "Savings", last4: "8823", balance: 8940.12 },
  { id: "sav-5679", type: "Savings", last4: "5679", balance: 1500.0 },
  { id: "cc-2502", type: "Credit card", last4: "2502", balance: -1175.27 },
];

const currentBalance = accounts.reduce((sum, account) => sum + account.balance, 0);

interface Payment {
  id: string;
  name: string;
  dueDate: Date;
  amount: number;
}

function daysFromToday(days: number) {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + days);
  return date;
}

// Placeholder until payments come from the API.
const payments: Payment[] = [
  { id: "rent", name: "Rent", dueDate: daysFromToday(3), amount: 1450.0 },
  { id: "car", name: "Car loan", dueDate: daysFromToday(6), amount: 312.5 },
  { id: "phone", name: "Phone bill", dueDate: daysFromToday(9), amount: 65.0 },
  { id: "internet", name: "Internet", dueDate: daysFromToday(12), amount: 59.99 },
  { id: "gym", name: "Gym membership", dueDate: daysFromToday(15), amount: 40.0 },
  { id: "insurance", name: "Car insurance", dueDate: daysFromToday(21), amount: 128.4 },
];

const today = new Date();
const dueThisMonth = payments
  .filter((p) => p.dueDate.getFullYear() === today.getFullYear() && p.dueDate.getMonth() === today.getMonth())
  .reduce((sum, p) => sum + p.amount, 0);

// Show only the next few payments, soonest first.
const upcomingPayments = [...payments].sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime()).slice(0, 4);

// What's left after this month's payments come out of the current balance.
const leftToSpend = currentBalance - dueThisMonth;

const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });

function BankIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M3 9.5 12 4l9 5.5" />
      <path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8" />
      <path d="M3 20h18" />
    </svg>
  );
}

export function Home() {
  const firstName = getSessionUser()?.first_name;

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-5">
        <Text variant="h2" as="h1">{firstName ? `Hello, ${firstName}` : "Hello"}</Text>

        <section aria-labelledby="current-balance-label" className="flex flex-col gap-1.5">
          <Text id="current-balance-label" variant="overline" tone="muted">
            Current balance
          </Text>
          <Text variant="h1" as="p" className="tabular-nums">
            {currency.format(currentBalance)}
          </Text>
        </section>
      </header>

      <div className="flex flex-col gap-6 md:flex-row md:items-start">
        <section aria-labelledby="accounts-heading" className="flex w-full max-w-lg flex-col gap-2 rounded-lg border border-blue-grey-700 px-4 pt-4 pb-1.5">
          <Text id="accounts-heading" variant="h4" as="h2">
            Accounts
          </Text>

          <ul className="flex flex-col">
            {accounts.map((account) => (
              <li key={account.id} className="flex items-center gap-3 py-2.5">
                <span
                  className={[
                    "grid size-9 shrink-0 place-items-center rounded-full border-2",
                    account.balance === 0 ? "border-blue-grey-700 text-blue-grey-600" : "border-blue-grey-300 text-blue-grey-100",
                  ].join(" ")}
                >
                  <BankIcon className="size-[1.125rem]" />
                </span>
                <span className="flex-1 truncate text-base text-blue-grey-100">
                  {account.type} <span className="text-blue-grey-400">••</span>
                  {account.last4}
                </span>
                <span
                  className={[
                    "text-base font-medium",
                    account.balance < 0 ? "text-red-vivid-300" : "text-blue-grey-050",
                  ].join(" ")}
                >
                  <Money amount={account.balance} />
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="payments-heading" className="flex w-full max-w-lg flex-col gap-2 rounded-lg border border-blue-grey-700 px-4 py-4">
          <Text id="payments-heading" variant="h4" as="h2">
            Upcoming payments
          </Text>

          <ul className="flex flex-col">
            {upcomingPayments.map((payment) => (
              <li key={payment.id} className="flex items-baseline gap-3 py-1">
                <span className="flex-1 truncate text-base text-blue-grey-100">
                  {payment.name} <span className="text-sm text-blue-grey-400">· Due {shortDate.format(payment.dueDate)}</span>
                </span>
                <span className="text-base font-medium text-blue-grey-050">
                  <Money amount={payment.amount} />
                </span>
              </li>
            ))}
          </ul>

          <p className="mt-2 flex justify-between gap-3 border-t border-blue-grey-700 pt-3 text-base">
            <span className="font-medium text-blue-grey-100">Left to spend</span>
            <span className={["font-medium", leftToSpend < 0 ? "text-red-vivid-300" : "text-blue-grey-050"].join(" ")}>
              <Money amount={leftToSpend} />
            </span>
          </p>
        </section>
      </div>
    </div>
  );
}

export default Home;
