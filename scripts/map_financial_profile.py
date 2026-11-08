"""Step 3: map profiles to Nessie seed plans and unified Waypoint profiles (no API calls).

Writes data/seed_plans/<id>.json and data/normalized/<id>.json.
"""
import argparse

from _common import GENERATED_DIR, NORMALIZED_DIR, SEED_PLANS_DIR, profile_ids, read_profile, write_json

from backend.mapping.missing_fields import GeneratedFields
from backend.mapping.normalize import build_unified_profile
from backend.mapping.pnc_to_nessie import build_seed_plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profile_ids", nargs="*", help="default: all generated profiles")
    for pid in ap.parse_args().profile_ids or profile_ids():
        profile = read_profile(pid)
        gen = GeneratedFields.model_validate_json((GENERATED_DIR / f"{pid}.json").read_text(encoding="utf-8"))
        plan = build_seed_plan(profile, gen)
        write_json(SEED_PLANS_DIR / f"{pid}.json", plan)
        write_json(NORMALIZED_DIR / f"{pid}.json", build_unified_profile(profile, gen, plan))
        print(f"{pid}: {len(plan.operations)} Nessie operations, {len(plan.skipped)} PNC-only rows kept locally")


if __name__ == "__main__":
    main()
