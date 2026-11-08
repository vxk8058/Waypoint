"""Shared helpers for scripts: import path, output locations, JSON writing."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
PROFILES_DIR = DATA / "profiles"
GENERATED_DIR = DATA / "generated"
SEED_PLANS_DIR = DATA / "seed_plans"
NORMALIZED_DIR = DATA / "normalized"
VALIDATION_DIR = DATA / "validation"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_profile(profile_id: str):
    from backend.schemas.student import StudentProfile
    return StudentProfile.model_validate_json((PROFILES_DIR / f"{profile_id}.json").read_text(encoding="utf-8"))


def profile_ids() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("stu-*.json"))
