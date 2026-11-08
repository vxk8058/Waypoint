# Waypoint API (Phase 4)

Run locally:

```bash
uvicorn backend.api.main:app --reload --port 8000
```

Interactive docs: `http://localhost:8000/docs`

## Authentication

Four hardcoded demo users, one per seeded student, are created in MongoDB `users` at startup.
All use the password `waypoint-demo` (override with `WAYPOINT_DEMO_PASSWORD`).

| Email | Student | Profile | What the data shows |
|---|---|---|---|
| `poyo@waypoint.demo` | Poyo de Avon | `stu-002` | No card or debt; saving for a first car |
| `lucas@waypoint.demo` | Lucas Patel | `stu-001` | Card paid in full; deferred student loan; emergency fund |
| `leah@waypoint.demo` | Leah Walker | `stu-003` | Auto loan; card balance carried; tight cash flow |
| `priya@waypoint.demo` | Priya Ramirez | `stu-004` | Freshman; aid refund; subsidized loan; card carried |

```http
POST /auth/login
{"email": "poyo@waypoint.demo", "password": "waypoint-demo"}
```

The response includes `access_token`, `expires_at` (12 hours) and `user`. Send the token on
every request as `Authorization: Bearer <token>`.

Tokens are HMAC-signed with `WAYPOINT_SESSION_SECRET`. If it is unset, a random secret is
used, so tokens stop working when the server restarts.

The student profile is always taken from the logged-in user. No endpoint accepts a
`profile_id` from the client.

## Endpoints

| Method and path | Returns |
|---|---|
| `GET /health` | MongoDB status, whether Nessie is configured |
| `POST /auth/login` | Token and user |
| `GET /auth/me` | Logged-in user |
| `GET /api/me/profile` | Full unified profile: user, accounts, transactions, bills, goal, monthly summary, wellness inputs, metadata |
| `GET /api/me/accounts` | Checking, savings, credit card and loans, each with its Nessie balance and PNC-only terms (APR, limit, APY) |
| `GET /api/me/transactions` | Newest first. Filters: `account_id`, `start_date`, `end_date`, `flow_class`, `category`, `limit` (1–500), `offset` |
| `GET /api/me/bills` | Recurring bills, soonest due first (due dates from Nessie), plus `monthly_total` |
| `GET /api/me/goal` | The one primary savings goal |
| `GET /api/me/summary` | Monthly income, spending, debt payments, interest, savings; wellness-engine inputs |

Every `/api/me/*` endpoint accepts `?refresh=true` to skip the cache and refetch from Nessie.

Every response except `/profile` includes a `data` block:

```json
{"profile_id": "stu-002", "data_mode": "nessie", "stale": false, "as_of_date": "2026-10-31",
 "fetched_at": "2026-11-08T01:09:05Z", "warnings": []}
```

- `data_mode: "nessie"`: banking data was read live from Nessie and merged with PNC-only data from MongoDB.
- `stale: true`: Nessie was unreachable, so the last saved snapshot is shown. `warnings` says why.
- `data_mode: "pre_seed"`: the profile is not in Nessie (or Nessie is not configured), so the stored pre-seed profile is shown.

## Where each value comes from

Each account, transaction and bill has `source.origin`:

| Origin | Examples |
|---|---|
| `nessie` | Balances, deposits, withdrawals, purchases, transfers, bills, loans, customer name and address |
| `pnc_generated` | Interest accruals, loan history, goal, student info, APR, credit limit |
| `derived` | Opening balances, monthly summary, wellness inputs |

Records created directly in Nessie (not by Waypoint) are still returned. Their category is
inferred and `source.note` says so.

## Transaction fields the frontend needs most

| Field | Meaning |
|---|---|
| `amount` | Always positive whole dollars |
| `direction` | `in` or `out` of that account |
| `flow_class` | `income`, `expense`, `internal_transfer` or `non_cash`. Use this to total income and spending without double counting. |
| `category` | E.g. `groceries`, `housing`, `goal_contribution`, `credit_card_payment` |
| `merchant_name` | For purchases |
| `transfer_id` | Shared by the two sides of an internal transfer |
| `bill_key` | Links a payment to its bill |

## Caching and Nessie usage

One Nessie fetch per profile (15–21 API calls, about 1 second) is cached for
`PROFILE_CACHE_TTL` seconds (default 300). Endpoints and calculations never call Nessie
directly. The API only reads from Nessie; it never writes.
