"""Step 1: generate synthetic student profiles (PNC conventions) -> data/profiles/."""
import argparse

from _common import PROFILES_DIR, write_json

from backend.generation.student_generator import DEFAULT_AS_OF, generate_all
from backend.validation.profile_validator import validate_profile


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    profiles = generate_all(DEFAULT_AS_OF)
    index = []
    for p in profiles:
        report = validate_profile(p)
        if not report.ok:
            raise SystemExit(f"{p.profile_id} failed validation: {report.errors[:3]}")
        write_json(PROFILES_DIR / f"{p.profile_id}.json", p)
        index.append({"profile_id": p.profile_id, "persona_key": p.persona_key, "is_primary_demo": p.is_primary_demo,
                      "school": p.student.school, "class_year": p.student.class_year,
                      "goal": p.goal.name, "transactions": len(p.transactions)})
        print(f"{p.profile_id} {'(primary demo) ' if p.is_primary_demo else ''}{p.student.school}: "
              f"{len(p.transactions)} transactions, {len(p.accounts)} accounts")
    write_json(PROFILES_DIR / "index.json", {"as_of_date": DEFAULT_AS_OF.isoformat(), "profiles": index})


if __name__ == "__main__":
    main()
