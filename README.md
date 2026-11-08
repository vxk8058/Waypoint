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
| 3 | Nessie seeding | Next |
| 4–7 | Retrieval, wellness engine, simulation, integration | Planned |

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

## Demo profiles

| ID | Student | Highlights |
|---|---|---|
| `stu-001` (primary) | UT Dallas junior, CS, library job + family support | Card paid in full, deferred unsubsidized loan, emergency-fund goal |
| `stu-002` | UNT sophomore, lives at home, retail job | No card, saving for a first car |
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
  pipeline.py   generate → fill → map → normalize → validate
scripts/        runnable pipeline steps
data/           generated sample outputs (committed)
docs/           DATA_MAPPING.md
third_party/pnc_wellness/   vendored PNC toolkit (Apache-2.0, unmodified)
tests/
```

See [docs/DATA_MAPPING.md](docs/DATA_MAPPING.md) for the field mapping and the verified
Nessie API behavior that shaped it.
