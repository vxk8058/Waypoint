"""Step 4: validate profiles + seed plans; optionally upsert everything into MongoDB.

Exit code 1 if any profile has errors.
"""
import argparse

from _common import VALIDATION_DIR, profile_ids, read_profile, write_json

from backend.pipeline import build_bundle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profile_ids", nargs="*", help="default: all generated profiles")
    ap.add_argument("--save-mongo", action="store_true", help="upsert profiles into MONGODB_URI")
    args = ap.parse_args()
    bundles = [build_bundle(read_profile(pid)) for pid in args.profile_ids or profile_ids()]
    failed = False
    for b in bundles:
        r = b.report
        write_json(VALIDATION_DIR / f"{r.profile_id}.json", r)
        print(f"{r.profile_id}: {'OK' if r.ok else 'FAILED'} - {len(r.checks_run)} checks, "
              f"{len(r.errors)} errors, {len(r.warnings)} warnings")
        for issue in r.errors + r.warnings:
            print(f"   [{issue.check}] {issue.message} {issue.record_id or ''}")
        failed |= not r.ok
    if args.save_mongo and not failed:
        from backend.database.mongo import check_connection, ensure_indexes, get_database, save_bundle
        db = get_database()
        try:
            check_connection(db)
        except RuntimeError as exc:
            raise SystemExit(f"MongoDB connection failed: {exc}") from None
        ensure_indexes(db)
        for b in bundles:
            save_bundle(db, b)
        print(f"Saved {len(bundles)} profiles to MongoDB database '{db.name}'")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
