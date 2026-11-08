# Waypoint

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
