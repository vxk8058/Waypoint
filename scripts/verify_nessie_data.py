"""Phase 3: read seeded data back from Nessie and verify it against the plan and ledger.

Writes data/verification/<id>.json, logs to MongoDB seed_runs and records the Nessie
customer id on the student document. Exit code 1 if any profile fails.
"""
import argparse
import uuid
from datetime import datetime, timezone

from _common import VERIFICATION_DIR, open_mongo, profile_ids, read_plan, read_profile, write_json

from backend.integrations.nessie.client import NessieClient
from backend.seeding.verifier import verify_profile


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profile_ids", nargs="*")
    args = ap.parse_args()
    db = open_mongo()
    failed = False
    with NessieClient() as client:
        for pid in args.profile_ids or profile_ids():
            report = verify_profile(read_profile(pid), read_plan(pid), client, db)
            write_json(VERIFICATION_DIR / f"{pid}_nessie.json", report)
            doc = report.model_dump(mode="json")
            db.seed_runs.insert_one({"run_id": f"verify-{uuid.uuid4().hex[:12]}", "type": "verify",
                                     "finished_at": datetime.now(timezone.utc), **doc})
            db.students.update_one({"profile_id": pid}, {"$set": {"nessie": {
                "customer_id": report.nessie_customer_id, "verified": report.ok,
                "verified_at": report.checked_at}}})
            print(f"{pid}: {'VERIFIED' if report.ok else 'FAILED'} - found {sum(report.found_counts.values())}/"
                  f"{sum(report.expected_counts.values())} records, {len(report.missing)} missing, "
                  f"{len(report.mismatches)} mismatched, {len(report.unexpected)} unexpected, "
                  f"{report.api_calls} API calls")
            for a in report.accounts:
                print(f"   {a.local_key}: balance {a.nessie_balance} (expected {a.expected_balance}), "
                      f"activity {a.nessie_net_activity} (ledger {a.ledger_net_activity}) {'ok' if a.ok else 'MISMATCH'}")
            for item in (report.missing + report.mismatches + report.unexpected)[:10]:
                print(f"   {item}")
            failed |= not report.ok
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
