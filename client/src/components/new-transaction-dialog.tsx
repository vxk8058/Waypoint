import { Fragment, useEffect, useRef, useState, type FormEvent } from "react";
import {
  createBill,
  createDeposit,
  createLoan,
  createPurchase,
  createTransfer,
  createWithdrawal,
  getMerchants,
  type Account,
  type LoanType,
  type Merchant,
} from "../lib/nessie";
import { accountLabel, transactionKinds, type TransactionKind } from "../lib/transactions";
import { Button } from "./button";
import { Select } from "./select";
import { Text } from "./text";
import { TextField } from "./text-field";

export interface NewTransactionDialogProps {
  open: boolean;
  onClose: () => void;
  /** Called after Nessie accepts the new transaction. */
  onCreated: () => void;
  account: Account;
  accounts: Account[];
  defaultKind?: TransactionKind;
}

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Merchants are global to the API key; load them once.
let merchantsPromise: Promise<Merchant[]> | null = null;
function loadMerchants() {
  merchantsPromise ??= getMerchants()
    .then((list) => list.filter((m) => m.name?.trim()).sort((a, b) => a.name.localeCompare(b.name)))
    .catch((err) => {
      merchantsPromise = null;
      throw err;
    });
  return merchantsPromise;
}

export function NewTransactionDialog({ open, onClose, onCreated, account, accounts, defaultKind = "deposit" }: NewTransactionDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<TransactionKind>(defaultKind);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [merchants, setMerchants] = useState<Merchant[] | null>(null);
  const [merchantError, setMerchantError] = useState<string | null>(null);

  const otherAccounts = accounts.filter((a) => a._id !== account._id);

  // Drive the native <dialog> from the `open` prop so Esc, focus trapping and the backdrop come for free.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setKind(defaultKind);
      setError(null);
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, defaultKind]);

  useEffect(() => {
    if (!open || kind !== "purchase" || merchants) return;
    loadMerchants().then(setMerchants, (err: Error) => setMerchantError(err.message));
  }, [open, kind, merchants]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const str = (name: string) => String(form.get(name) ?? "").trim();
    const num = (name: string) => Number(form.get(name));
    const optional = (name: string) => str(name) || undefined;

    setSubmitting(true);
    setError(null);
    try {
      const id = account._id;
      switch (kind) {
        case "deposit":
          await createDeposit(id, { amount: num("amount"), description: optional("description"), transaction_date: optional("date") });
          break;
        case "withdrawal":
          await createWithdrawal(id, { amount: num("amount"), description: optional("description"), transaction_date: optional("date") });
          break;
        case "transfer":
          await createTransfer(id, {
            payee_id: str("payee_id"),
            amount: num("amount"),
            description: optional("description"),
            transaction_date: optional("date"),
          });
          break;
        case "purchase":
          await createPurchase(id, {
            merchant_id: str("merchant_id"),
            amount: num("amount"),
            description: optional("description"),
            purchase_date: optional("date"),
          });
          break;
        case "bill": {
          const recurring = optional("recurring_date");
          await createBill(id, {
            payee: str("payee"),
            nickname: optional("nickname"),
            payment_amount: num("amount"),
            payment_date: optional("date"),
            ...(recurring ? { status: "recurring", recurring_date: Number(recurring) } : {}),
          });
          break;
        }
        case "loan":
          await createLoan(id, {
            type: str("loan_type") as LoanType,
            amount: num("amount"),
            monthly_payment: num("monthly_payment"),
            credit_score: num("credit_score"),
            description: optional("description"),
          });
          break;
      }
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  const amountField = (label = "Amount") => (
    <TextField
      name="amount"
      label={label}
      type="number"
      inputMode="decimal"
      min="0.01"
      step="0.01"
      required
      fullWidth
      leading="$"
      placeholder="0.00"
    />
  );
  const dateField = (label = "Date") => <TextField name="date" label={label} type="date" defaultValue={todayISO()} fullWidth />;
  const descriptionField = <TextField name="description" label="Description" placeholder="Optional" maxLength={140} fullWidth />;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={(e) => e.target === dialogRef.current && onClose()}
      aria-labelledby="new-transaction-title"
      className="m-auto w-full max-w-md rounded-lg border border-blue-grey-700 bg-surface p-0 text-blue-grey-050 backdrop:bg-canvas/70 backdrop:backdrop-blur-sm"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-1">
          <Text id="new-transaction-title" variant="h4" as="h2">
            New transaction
          </Text>
          <Text variant="small" tone="muted">
            From {accountLabel(account)}
          </Text>
        </div>

        <Select label="Type" value={kind} onChange={(e) => setKind(e.target.value as TransactionKind)} fullWidth>
          {transactionKinds.map((t) => (
            <option key={t.kind} value={t.kind}>
              {t.label}
            </option>
          ))}
        </Select>

        {/* Remount the fields per type so values typed for another type never carry over. */}
        <Fragment key={kind}>
        {(kind === "deposit" || kind === "withdrawal") && (
          <>
            {amountField()}
            {dateField()}
            {descriptionField}
          </>
        )}

        {kind === "transfer" &&
          (otherAccounts.length === 0 ? (
            <Text variant="small" tone="muted">
              You need a second account to transfer money.
            </Text>
          ) : (
            <>
              <Select name="payee_id" label="To account" required fullWidth defaultValue="">
                <option value="" disabled>
                  Choose an account
                </option>
                {otherAccounts.map((a) => (
                  <option key={a._id} value={a._id}>
                    {accountLabel(a)}
                  </option>
                ))}
              </Select>
              {amountField()}
              {dateField()}
              {descriptionField}
            </>
          ))}

        {kind === "purchase" && (
          <>
            <Select
              name="merchant_id"
              label="Merchant"
              required
              fullWidth
              defaultValue=""
              disabled={!merchants}
              error={merchantError ?? undefined}
            >
              <option value="" disabled>
                {merchants ? "Choose a merchant" : "Loading merchants…"}
              </option>
              {merchants?.map((m) => (
                <option key={m._id} value={m._id}>
                  {m.name}
                </option>
              ))}
            </Select>
            {amountField()}
            {dateField()}
            {descriptionField}
          </>
        )}

        {kind === "bill" && (
          <>
            <TextField name="payee" label="Payee" placeholder="e.g. Comcast" required fullWidth />
            <TextField name="nickname" label="Nickname" placeholder="Optional, e.g. Internet" fullWidth />
            {amountField("Payment amount")}
            {dateField("Payment date")}
            <TextField
              name="recurring_date"
              label="Repeats monthly on day"
              type="number"
              min="1"
              max="31"
              placeholder="Leave blank for a one-time bill"
              fullWidth
            />
          </>
        )}

        {kind === "loan" && (
          <>
            <Select name="loan_type" label="Loan type" required fullWidth defaultValue="auto">
              <option value="auto">Auto</option>
              <option value="home">Home</option>
              <option value="small business">Small business</option>
            </Select>
            {amountField("Loan amount")}
            <TextField
              name="monthly_payment"
              label="Monthly payment"
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              required
              fullWidth
              leading="$"
              placeholder="0.00"
            />
            <TextField name="credit_score" label="Credit score" type="number" min="300" max="850" required fullWidth placeholder="300–850" />
            {descriptionField}
          </>
        )}

        </Fragment>

        {error && (
          <p role="alert" className="rounded-lg border border-red-vivid-700 bg-red-vivid-900/30 px-3 py-2 text-sm text-red-vivid-200">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting || (kind === "transfer" && otherAccounts.length === 0)}>
            {submitting ? "Saving…" : "Add transaction"}
          </Button>
        </div>
      </form>
    </dialog>
  );
}

export default NewTransactionDialog;
