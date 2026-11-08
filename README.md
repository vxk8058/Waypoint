# Waypoint
An app for reaching your financial goals

*Your financial life. One place. A clearer direction.*

An AI-powered financial intelligence backend for college students, built on the PNC
Financial Wellness toolkit, Capital One's Nessie API and NVIDIA Nemotron.

Pipeline: **PNC-convention synthetic data → mapping → Nessie seeding → Nessie retrieval →
unified profile → wellness engine → LangGraph + Nemotron simulation.**

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository and API inspection | Done |
| 2 | Student profile generation, mapping, validation | Done |
| 3 | Nessie seeding and verification | Done |
| 4 | Nessie retrieval, unified profile, API with demo login | Done |
| 5 | Financial wellness engine | Next |
| 6–7 | Simulation, integration | Planned |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in NESSIE_API_KEY and MONGODB_URI
```

`.env` is gitignored. Secrets are read from the environment only (`backend/config.py`).
MongoDB Atlas: URL-encode special characters in the password (`,` → `%2C`), and allow your IP
under Atlas → Network Access.

### Banking agent

A read-only LangGraph agent answers questions about the signed-in user's accounts.

```bash
curl -X POST localhost:8000/api/me/agent -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"question": "Where did my money go in October?"}'
```

- **Setup:** set `NVIDIA_API_KEY`, `PLANNER_MODEL` and `WORKER_MODEL` in `.env` (exact IDs from NVIDIA's
  model catalog). Models load on the first question; without them the endpoint returns a fallback answer
  with a "Query routing is unavailable" caveat. Other routes and the tests don't need these settings.
- **Flow** (`backend/agent/graph.py`): the planner routes the question to the Checking, Savings, Credit Card
  and Loans branches (in parallel); Verify checks the combined results and can re-fetch products or extra
  data (transactions, student bio) for at most three rounds; Gen UI returns an AI document.
- **Data:** branches read through the existing `ProfileService`, so Nessie caching, stale-snapshot fallback,
  pre-seed mode and warnings apply. Only GET requests are made. The profile always comes from the bearer
  token; the request body accepts only `question`. Warnings become caveats in the answer.
- **Numbers:** amounts are computed in code. The model writes text with `{fact_key}` placeholders that code
  fills in; any digit it types is rejected (one retry, then a code-only fallback).
- **Output:** `{"blocks": [...]}` validated against the frontend's
  `backend/agent/ui/ai-document.schema.json` (copied from the frontend; replace it when that schema changes).
- **Logs:** `waypoint.agent` logs each request's path (nodes, routes, Verify rounds) without question text,
  IDs or amounts. Don't enable `LANGSMITH_TRACING`: it would send full prompts with account data.
- **Status:** see `docs/BANKING_AGENT_CHECKLIST.md`. Live Nemotron runs and frontend rendering are unverified.

## Phase 2 pipeline

```bash
python scripts/generate_pnc_profiles.py     # data/profiles/     student profiles (PNC conventions)
python scripts/generate_missing_fields.py   # data/generated/    Nessie-only fields
python scripts/map_financial_profile.py     # data/seed_plans/   Nessie requests; data/normalized/ unified profiles
python scripts/validate_profile.py          # data/validation/   consistency reports
python scripts/validate_profile.py --save-mongo   # also upsert into MONGODB_URI
python -m pytest
```

Generation is deterministic, so re-running produces identical files.

## Phase 3: seed and verify Nessie

```bash
python scripts/seed_nessie.py               # all profiles; safe to re-run
python scripts/verify_nessie_data.py        # read back from Nessie and reconcile
python scripts/seed_nessie.py stu-001 --reset --yes   # delete stu-001's Nessie accounts/records, reseed
```

- Seeding is idempotent. Each plan step has a stable key. Nessie ids are stored in MongoDB
  (`nessie_id_map`) the moment they are created, and exported to `data/local/nessie/` (gitignored).
- If MongoDB has no id for a step (fresh database, crash, another machine), the seeder finds
  the existing Nessie record by its `[wp:...]` marker and reuses it instead of duplicating it.
- Verification checks every record and field, account balances, each account's net activity
  against the ledger, monthly income, and stray marker-tagged records. Reports go to
  `data/local/verification/` (gitignored) and the `seed_runs` collection.
- Seeding is a setup step only. Simulations never write to Nessie.

## Phase 4: run the API

```bash
python scripts/validate_profile.py --save-mongo   # profiles in MongoDB
python scripts/seed_nessie.py                     # Nessie ids in MongoDB
uvicorn backend.api.main:app --reload --port 8000
```

Log in at `http://localhost:8000/docs` with **poyo@waypoint.demo / waypoint-demo**. This
demo user is linked to `stu-002`, Poyo de Avon. Banking data is read live from Nessie and
merged with PNC-only data from MongoDB. See [docs/API.md](docs/API.md).

## Demo profiles

| ID | Student | Highlights |
|---|---|---|
| `stu-001` (primary) | UT Dallas junior, CS, library job + family support | Card paid in full, deferred unsubsidized loan, emergency-fund goal |
| `stu-002` (demo login) | Poyo de Avon, UNT sophomore, lives at home, retail job | No card, saving for a first car |
| `stu-003` | Texas A&M senior, co-op internship | Auto loan, card carried at ~28% utilization, relocation goal |
| `stu-004` | UT Austin freshman, dining job + aid refund | Subsidized loan, card carried, tuition-gap goal |

## Layout

```
backend/
  generation/   student generator (PNC conventions), personas, merchant catalog
  mapping/      Nessie-only field generation, PNC→Nessie seed plan, unified profile
  validation/   financial consistency checks
  schemas/      Pydantic models (student profile, Nessie bodies, seed plan, unified profile)
  database/     MongoDB persistence (students, goals, seed_plans, nessie_id_map, seed_runs)
  integrations/nessie/  Nessie HTTP client, response schemas, retrieval gateway
  seeding/      idempotent Nessie seeder, reset, read-back verifier
  services/     ProfileService: cached Nessie retrieval with snapshot and pre-seed fallbacks
  auth/         demo user, password hashing, signed session tokens
  api/          FastAPI app (uvicorn backend.api.main:app)
  pipeline.py   generate → fill → map → normalize → validate
scripts/        runnable pipeline steps
data/           generated sample outputs (committed); data/local/ holds run reports and id maps (gitignored)
docs/           DATA_MAPPING.md
third_party/pnc_wellness/   vendored PNC toolkit (Apache-2.0, unmodified)
tests/
```

See [docs/DATA_MAPPING.md](docs/DATA_MAPPING.md) for the field mapping and the verified
Nessie API behavior that shaped it.


# 1. Install dependencies in a virtual environment (one time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set up the data (one time; it's safe to run again)
python scripts/validate_profile.py --save-mongo   # saves the student profiles to MongoDB
python scripts/seed_nessie.py                     # creates their accounts in Nessie

# 3. Start the API
python -m uvicorn backend.api.main:app --reload --port 8000
