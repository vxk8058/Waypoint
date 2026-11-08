import { useState, type ReactNode, type SVGProps } from "react";
import { useSearchParams } from "react-router";
import { Button } from "../components/button";
import { Money } from "../components/money";
import { ChevronDownIcon } from "../components/select";
import { Text } from "../components/text";
import { fetchAccounts, signedBalance } from "../lib/accounts";
import { getAccountTransactions, humanize, transactionKinds, type Transaction, type TransactionKind } from "../lib/transactions";
import { useAsync } from "../lib/use-async";

// ---------- Icons ----------

function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

const kindIcons: Record<TransactionKind, ReactNode> = {
  // Arrow into a tray
  deposit: (
    <>
      <path d="M12 4v10M8 10l4 4 4-4" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  // Arrow out of a tray
  withdrawal: (
    <>
      <path d="M12 14V4M8 8l4-4 4 4" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  transfer: <path d="M7 4 3 8l4 4M3 8h14M17 12l4 4-4 4M21 16H7" />,
  // Shopping bag
  purchase: (
    <>
      <path d="M5 8h14l-1 12H6L5 8Z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </>
  ),
  // Receipt
  bill: (
    <>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" />
      <path d="M9 8h6M9 12h6" />
    </>
  ),
  // Percent sign
  interest: (
    <>
      <path d="M19 5 5 19" />
      <circle cx="7" cy="7" r="2.5" />
      <circle cx="17" cy="17" r="2.5" />
    </>
  ),
};

// ---------- Formatting ----------

const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const longDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });

function formatDay(date: Date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - date.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days === -1) return "Tomorrow";
  return date.getFullYear() === today.getFullYear() ? shortDate.format(date) : longDate.format(date);
}

// ---------- Rows ----------

function TransactionRow({ transaction: t }: { transaction: Transaction }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span className="grid size-9 shrink-0 place-items-center rounded-full border-2 border-blue-grey-300 text-blue-grey-100">
        <Icon className="size-[1.125rem]">{kindIcons[t.kind]}</Icon>
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-base text-blue-grey-100">{t.title}</span>
        <span className="truncate text-sm text-blue-grey-400">
          {t.category} · {formatDay(t.date)}
        </span>
      </span>
      <span className={["self-start pt-0.5 text-base font-medium", t.amount > 0 ? "text-teal-300" : "text-blue-grey-050"].join(" ")}>
        <Money amount={t.amount} signed />
      </span>
    </li>
  );
}

function SkeletonRows() {
  return (
    <ul aria-hidden="true" className="flex flex-col">
      {[0, 1, 2, 3].map((i) => (
        <li key={i} className="flex items-center gap-3 py-2.5">
          <span className="size-9 shrink-0 animate-pulse rounded-full bg-surface-raised" />
          <span className="flex flex-1 flex-col gap-1.5">
            <span className="h-4 w-40 animate-pulse rounded bg-surface-raised" />
            <span className="h-3 w-24 animate-pulse rounded bg-surface-raised" />
          </span>
          <span className="h-4 w-16 animate-pulse rounded bg-surface-raised" />
        </li>
      ))}
    </ul>
  );
}

function Notice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 py-10 text-center">
      <Text variant="body" weight="medium">
        {title}
      </Text>
      <Text variant="small" tone="muted" className="max-w-sm">
        {children}
      </Text>
    </div>
  );
}

// ---------- Page ----------

type Filter = TransactionKind | "all";

const PAGE_SIZE = 20;

export function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");

  const accounts = useAsync(fetchAccounts, []);
  const accountList = accounts.data?.accounts ?? [];
  // The selected account lives in the URL (?account=…) so it survives reloads and can be linked to.
  const account = accountList.find((a) => a.account_id === searchParams.get("account")) ?? accountList[0];

  const transactions = useAsync(
    () => (account ? getAccountTransactions(account.account_id) : Promise.resolve([])),
    [account?.account_id],
  );

  const visible = (transactions.data ?? []).filter((t) => filter === "all" || t.kind === filter);

  // How many rows to show; goes back to the first page whenever the account or filter changes.
  const listKey = `${account?.account_id}|${filter}`;
  const [shown, setShown] = useState({ key: listKey, count: PAGE_SIZE });
  const count = shown.key === listKey ? shown.count : PAGE_SIZE;
  const remaining = visible.length - count;

  function selectAccount(id: string) {
    setSearchParams(
      (params) => {
        params.set("account", id);
        return params;
      },
      { replace: true },
    );
  }

  let body: ReactNode;
  if (accounts.error) {
    body = <Notice title="Couldn't load your accounts">{accounts.error.message}</Notice>;
  } else if (!accounts.loading && !account) {
    body = <Notice title="No accounts yet">Accounts linked to your profile will show up here.</Notice>;
  } else if (transactions.error) {
    body = <Notice title="Couldn't load transactions">{transactions.error.message}</Notice>;
  } else if (!account || !transactions.data) {
    body = <SkeletonRows />;
  } else if (visible.length === 0) {
    body = (
      <Notice title={filter === "all" ? "No transactions yet" : `No ${transactionKinds.find((t) => t.kind === filter)?.plural.toLowerCase()}`}>
        Activity on this account will show up here.
      </Notice>
    );
  } else {
    body = (
      <>
        <ul className="flex flex-col">
          {visible.slice(0, count).map((t) => (
            <TransactionRow key={t.id} transaction={t} />
          ))}
        </ul>
        {remaining > 0 && (
          <div className="flex justify-center border-t border-blue-grey-700 py-3">
            <Button variant="ghost" size="sm" onClick={() => setShown({ key: listKey, count: count + PAGE_SIZE })}>
              Show more ({remaining} left)
            </Button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      <Text variant="h2" as="h1">
        Transactions
      </Text>

      <section aria-labelledby="account-balance-label" className="flex flex-col gap-4 rounded-lg border border-blue-grey-700 px-4 pt-4 pb-1.5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <Text id="account-balance-label" variant="overline" tone="muted">
              Balance
            </Text>
            <Text variant="h1" as="p" className="tabular-nums" aria-live="polite">
              {account ? <Money amount={signedBalance(account)} /> : <span className="text-blue-grey-600">—</span>}
            </Text>

            {accountList.length > 0 && (
              // Native select styled as inline text, like the account switcher in the mock.
              <label className="relative -ml-1 inline-flex w-fit items-center rounded-lg text-blue-grey-300 transition-colors focus-within:ring-2 focus-within:ring-purple-400/40 hover:text-blue-grey-100">
                <span className="sr-only">Account</span>
                <select
                  value={account?.account_id}
                  onChange={(e) => selectAccount(e.target.value)}
                  className="cursor-pointer appearance-none bg-transparent py-0.5 pr-6 pl-1 text-base outline-none"
                >
                  {accountList.map((a) => (
                    <option key={a.account_id} value={a.account_id} className="bg-surface text-blue-grey-050">
                      {a.name} · {humanize(a.type)}
                    </option>
                  ))}
                </select>
                <ChevronDownIcon className="pointer-events-none absolute right-1 size-4" />
              </label>
            )}
          </div>
        </header>

        <div role="group" aria-label="Filter by type" className="flex flex-wrap gap-1.5">
          {([{ kind: "all", plural: "All" }, ...transactionKinds] as const).map((t) => {
            const active = filter === t.kind;
            return (
              <button
                key={t.kind}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(t.kind)}
                className={[
                  "h-8 cursor-pointer rounded-full border px-3 text-sm font-medium transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/60",
                  active
                    ? "border-blue-grey-300 bg-surface-raised text-blue-grey-050"
                    : "border-blue-grey-700 text-blue-grey-300 hover:bg-surface hover:text-blue-grey-050",
                ].join(" ")}
              >
                {t.plural}
              </button>
            );
          })}
        </div>

        <div aria-busy={transactions.loading} className="border-t border-blue-grey-700 pt-1.5 pb-1.5">
          {body}
        </div>
      </section>
    </div>
  );
}

export default Transactions;
