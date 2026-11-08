# PNC → Nessie data mapping

How Waypoint turns PNC-convention synthetic student profiles into Nessie records, and
which data stays in Waypoint (MongoDB). Implemented in `backend/mapping/`.

## Verified Nessie API behavior (live API, Phase 1)

The published spec (`prod.nessieisreal.com/nessie-openapi-spec.yaml`) is incomplete. These
behaviors were verified against `prod-api.nessieisreal.com` with a throwaway customer:

| Behavior | Consequence for Waypoint |
|---|---|
| Decimal amounts and balances are silently truncated (500.75 → 500) | All amounts are whole dollars, everywhere |
| Deposits, withdrawals, purchases and transfers never change account balances | Accounts are created with the **closing** balance; transactions are history records |
| `PUT /accounts/{id}` ignores `balance` | Changing a balance means deleting and recreating the account |
| `POST` returns `objectCreated._id` (spec says a plain string) | IDs are persisted straight from the create response |
| Purchases and transfers can be created (missing from the spec); purchases use `purchase_date` | Bodies follow the live schema (`backend/schemas/nessie.py`) |
| Transfers reject `medium` and `payee_id`; they have no destination account | Each transfer leg is recorded on its own account; pairing lives in Waypoint |
| `GET /accounts/{id}/transfers` returns `id`, not `_id` | The client normalizes this (Phase 4) |
| Deleting an account does not delete its transactions; customers and merchants can't be deleted | Resets delete each record by stored id; customers and merchants are reused |
| Several `GET` endpoints accept invalid keys, and `/enterprise/*` lists all users' data | Seeded data is fully synthetic (fictional names, merchants, addresses) |

## A. Common fields (PNC value → Nessie)

| PNC-convention record | Nessie resource | Field mapping |
|---|---|---|
| account `checking` / `savings` / `credit_card` | Account `Checking` / `Savings` / `Credit Card` | `name` + marker → `nickname`; closing `balance` → `balance` |
| account `student_loan` / `auto_loan` | Loan on the checking account | `balance` → `amount`; `monthly_payment` → `monthly_payment`; `loan_status` → `status` |
| `income` row | Deposit | `posted_date` → `transaction_date`, `amount`, `description` |
| `expense` row with a merchant (checking or card) | Purchase | `merchant_key` → `merchant_id`, `posted_date` → `purchase_date`, `amount`, `description` |
| `expense` row for a bill payment or ATM cash | Withdrawal | `posted_date` → `transaction_date`, `amount`, `description` |
| `internal_transfer` leg on a Nessie account | Transfer (one per leg) | `posted_date`, `amount`, `description` + direction |
| recurring bill | Bill (`recurring`) on the paying account | `payee`, `nickname`, `amount` → `payment_amount`, `day_of_month` → `recurring_date` |
| merchant name and category | Merchant | `name`, `category` |

Every nickname or description carries a stable marker, e.g. `[wp:stu-001-T00042]`, used to
detect duplicates when seeding runs again.

## B. Nessie-only fields (Waypoint-generated, `backend/mapping/missing_fields.py`)

| Field | Rule (deterministic per profile) |
|---|---|
| Customer `first_name`, `last_name` | Fictional name pool, seeded by the profile |
| Customer `address` | In the student's school city |
| Merchant `address`, `geocode` | Near the city centre, seeded by the merchant key |
| Account `rewards` | Card: 1 point per dollar of card purchases in history; others 0 |
| Loan `credit_score` | 640–680 thin-file range, minus 25 if card utilization is above 30% |
| Loan `type` | `student` / `auto` |
| Transaction `medium` / `status` | `balance` / `completed` |
| Bill `status`, `payment_date` | `recurring`; next due date after the as-of date |

## C. PNC-only fields (kept in Waypoint / MongoDB)

APR, APY, credit limit, minimum/monthly payment schedules, loan subsidy and deferment status,
repayment estimate, `opening_balance`, `flow_class`, `transfer_id` pairing, `balance_after`,
interest accruals (`non_cash` rows), loan-account ledger rows, monthly statements, planning
assumptions (`monthly_income`, `monthly_non_debt_expenses`), student info (school, year,
major, employment), the primary goal, and validation reports.

## Source metadata

| Origin | Meaning |
|---|---|
| `pnc_generated` | From the student generator built on PNC conventions (`backend/generation`) |
| `nessie` | Retrieved from the Nessie API (Phase 4) |
| `waypoint_generated` | Filler that Nessie requires but PNC lacks |
| `derived` | Calculated: balances, statements, rewards, `goal.current_saved`, summaries |

## Counting rules (no double counting)

Same rules as PNC `Lab_Package/financial_tools.summarize_transaction_history`:

- Income = `income` rows only. Transfers, card payments and loan payments are never income.
- Spending = `expense` rows only. Card purchases count once; the card payment is a transfer.
- Bills are schedules (obligations for forecasting). Only their payment rows count as spending.
- Debt payments count on the liability side only.
- Interest and fees are reported separately; savings interest is non-cash.
- The goal earmark (`current_saved`) is part of the savings balance, never all of it.

## Seeding (Phase 3)

| Concern | Approach |
|---|---|
| Order | Customer → merchants → accounts → loans → bills → transactions (chronological) |
| Duplicates | Use the stored id; else adopt a Nessie record with the same marker (customers and merchants: same name and address); else create |
| Crashes | Each id is saved right after its create call, so a re-run resumes where it stopped |
| Ambiguous failures | A POST that times out or returns 5xx is not blindly retried: Nessie is re-checked for the marker first |
| Stale ids | `--revalidate` GETs each stored id and recreates records deleted in Nessie |
| Reset | `--reset` deletes the profile's marker-tagged records under its accounts, then the accounts (Nessie does not cascade); customers and merchants are kept and reused |
| Bills | Nessie computes `upcoming_payment_date` itself from today's date; use it for upcoming obligations |
