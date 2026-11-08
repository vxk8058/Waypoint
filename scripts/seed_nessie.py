"""Phase 3: seed Nessie from data/seed_plans/ (idempotent; safe to re-run).

    python scripts/seed_nessie.py                 # all profiles
    python scripts/seed_nessie.py stu-001         # one profile
    python scripts/seed_nessie.py stu-001 --reset --yes   # delete this profile's Nessie accounts
                                                          # and records, then seed again

Nessie ids are stored in MongoDB (nessie_id_map) and exported to data/nessie/.
"""
import argparse
import uuid
from datetime import datetime, timezone

from _common import NESSIE_DIR, open_mongo, profile_ids, read_plan, write_json

from backend.integrations.nessie.client import NessieClient
from backend.seeding.seeder import GLOBAL, Seeder


def export_id_map(db, plan):
    merchant_keys = [op.local_key for op in plan.operations if op.resource == "merchant"]
    rows = list(db.nessie_id_map.find({"$or": [{"profile_id": plan.profile_id},
                                               {"profile_id": GLOBAL, "local_key": {"$in": merchant_keys}}]},
                                      {"_id": 0, "local_key": 1, "resource": 1, "nessie_id": 1, "source_record_id": 1}))
    rows.sort(key=lambda r: [op.local_key for op in plan.operations].index(r["local_key"])
              if r["local_key"] in {op.local_key for op in plan.operations} else 10**6)
    customer = next((r["nessie_id"] for r in rows if r["resource"] == "customer"), None)
    write_json(NESSIE_DIR / f"{plan.profile_id}_id_map.json",
               {"profile_id": plan.profile_id, "nessie_customer_id": customer, "records": rows})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile_ids", nargs="*")
    ap.add_argument("--reset", action="store_true", help="delete the profile's Nessie accounts and records first")
    ap.add_argument("--yes", action="store_true", help="confirm --reset without prompting")
    ap.add_argument("--revalidate", action="store_true", help="GET every mapped id before trusting it")
    ap.add_argument("--continue-on-error", action="store_true")
    args = ap.parse_args()

    db = open_mongo()
    ids = args.profile_ids or profile_ids()
    failed = False
    with NessieClient() as client:
        seeder = Seeder(client, db, revalidate=args.revalidate)
        for pid in ids:
            plan = read_plan(pid)
            run = {"run_id": f"seed-{uuid.uuid4().hex[:12]}", "type": "seed", "profile_id": pid,
                   "started_at": datetime.now(timezone.utc)}
            if args.reset:
                if not args.yes and input(f"Delete Nessie accounts and records for {pid}? [y/N] ").lower() != "y":
                    raise SystemExit("aborted")
                run["reset"] = seeder.reset(pid)
                print(f"{pid}: reset {run['reset']}")
            result = seeder.seed(plan, stop_on_error=not args.continue_on_error,
                                 progress=lambda i, n, r: print(f"  {pid}: {i}/{n} (created {r.created}, "
                                                                f"adopted {r.adopted}, existing {r.existing})"))
            run.update(finished_at=datetime.now(timezone.utc), ok=result.ok, created=result.created,
                       adopted=result.adopted, existing=result.existing, updated=result.updated,
                       failed=result.failed,
                       by_resource=result.by_resource, errors=result.errors, warnings=result.warnings,
                       api_calls=client.calls)
            db.seed_runs.insert_one(run)
            export_id_map(db, plan)
            print(f"{pid}: {'OK' if result.ok else 'FAILED'} - created {result.created}, adopted {result.adopted}, "
                  f"existing {result.existing}, updated {result.updated}, failed {result.failed}")
            for item in result.errors + result.warnings:
                print(f"   {item}")
            failed |= not result.ok
            if failed and not args.continue_on_error:
                break
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
