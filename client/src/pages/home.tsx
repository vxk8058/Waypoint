import type { SVGProps } from "react";
import { BalanceHistory } from "../components/balance-history";
import { Money } from "../components/money";
import { Text } from "../components/text";
import { currentBalance, fetchAccounts, signedBalance } from "../lib/accounts";
import { getSessionUser } from "../lib/api";
import { fetchBills, parseDate } from "../lib/bills";
import { useAsync } from "../lib/use-async";

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

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
  const { data, error, loading } = useAsync(fetchAccounts, []);
  const accounts = data?.accounts ?? [];
  const balance = data ? currentBalance(accounts) : undefined;
  const bills = useAsync(fetchBills, []);
  // Show only the next few payments, soonest first (the API already sorts by due date).
  const upcomingPayments = bills.data?.bills.slice(0, 4) ?? [];
  // What's left once a month of bills comes out of the current balance.
  const leftToSpend = balance !== undefined && bills.data ? balance - bills.data.monthly_total : undefined;

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="flex w-full flex-col gap-5 lg:w-sm lg:shrink-0">
          <Text variant="h2" as="h1">{firstName ? `Hello, ${firstName}` : "Hello"}</Text>

          <section aria-labelledby="current-balance-label" className="flex flex-col gap-1.5">
            <Text id="current-balance-label" variant="overline" tone="muted">
              Current balance
            </Text>
            <Text variant="h1" as="p" className="tabular-nums">
              {balance !== undefined ? currency.format(balance) : loading ? "…" : "—"}
            </Text>
          </section>

          <section aria-labelledby="accounts-heading" className="flex w-full flex-1 flex-col gap-2 rounded-lg border border-blue-grey-700 px-4 pt-4 pb-1.5">
            <Text id="accounts-heading" variant="h4" as="h2">
              Accounts
            </Text>

            {loading && !data && <p className="py-2.5 text-sm text-blue-grey-400">Loading accounts…</p>}
            {error && (
              <p role="alert" className="py-2.5 text-sm text-red-vivid-300">
                Couldn't load accounts: {error.message}
              </p>
            )}
            {data && accounts.length === 0 && <p className="py-2.5 text-sm text-blue-grey-400">No accounts yet.</p>}

            <ul className="flex flex-col">
              {accounts.map((account) => {
                const amount = signedBalance(account);
                return (
                  <li key={account.account_id} className="flex items-center gap-3 py-2.5">
                    <span
                      className={[
                        "grid size-9 shrink-0 place-items-center rounded-full border-2",
                        amount === 0 ? "border-blue-grey-700 text-blue-grey-600" : "border-blue-grey-300 text-blue-grey-100",
                      ].join(" ")}
                    >
                      <BankIcon className="size-[1.125rem]" />
                    </span>
                    <span className="flex-1 truncate text-base text-blue-grey-100">{account.name}</span>
                    <span className={["text-base font-medium", amount < 0 ? "text-red-vivid-300" : "text-blue-grey-050"].join(" ")}>
                      <Money amount={amount} />
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>

        {data && <BalanceHistory accounts={accounts} asOf={data.data.as_of_date} className="w-full min-w-0 flex-1 lg:max-w-xl" />}
      </div>

      <div className="flex flex-col gap-6 md:flex-row md:items-start">
        <section aria-labelledby="payments-heading" className="flex w-full max-w-lg flex-col gap-2 rounded-lg border border-blue-grey-700 px-4 py-4">
          <Text id="payments-heading" variant="h4" as="h2">
            Upcoming payments
          </Text>

          {bills.loading && !bills.data && <p className="py-1 text-sm text-blue-grey-400">Loading payments…</p>}
          {bills.error && (
            <p role="alert" className="py-1 text-sm text-red-vivid-300">
              Couldn't load payments: {bills.error.message}
            </p>
          )}
          {bills.data && upcomingPayments.length === 0 && <p className="py-1 text-sm text-blue-grey-400">No upcoming payments.</p>}

          <ul className="flex flex-col">
            {upcomingPayments.map((bill) => (
              <li key={bill.bill_key} className="flex items-baseline gap-3 py-1">
                <span className="flex-1 truncate text-base text-blue-grey-100" title={bill.payee}>
                  {bill.nickname || bill.payee} <span className="text-sm text-blue-grey-400">· Due {shortDate.format(parseDate(bill.next_due_date))}</span>
                </span>
                <span className="text-base font-medium text-blue-grey-050">
                  <Money amount={bill.amount} />
                </span>
              </li>
            ))}
          </ul>

          <p className="mt-2 flex justify-between gap-3 border-t border-blue-grey-700 pt-3 text-base">
            <span className="font-medium text-blue-grey-100">Left to spend</span>
            <span className={["font-medium", leftToSpend !== undefined && leftToSpend < 0 ? "text-red-vivid-300" : "text-blue-grey-050"].join(" ")}>
              {leftToSpend !== undefined ? <Money amount={leftToSpend} /> : "—"}
            </span>
          </p>
        </section>
      </div>
    </div>
  );
}

export default Home;
