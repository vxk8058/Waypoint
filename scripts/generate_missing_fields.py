"""Step 2: generate Nessie-only fields (names, address, rewards, credit score) -> data/generated/."""
import argparse

from _common import GENERATED_DIR, profile_ids, read_profile, write_json

from backend.mapping.missing_fields import generate_missing_fields


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profile_ids", nargs="*", help="default: all generated profiles")
    for pid in ap.parse_args().profile_ids or profile_ids():
        gen = generate_missing_fields(read_profile(pid))
        write_json(GENERATED_DIR / f"{pid}.json", gen)
        print(f"{pid}: {gen.customer.first_name} {gen.customer.last_name}, {gen.customer.city}")


if __name__ == "__main__":
    main()
