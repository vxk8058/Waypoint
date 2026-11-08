"""The committed sample data must match what the pipeline generates (no stale files)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_committed_files_match_pipeline(bundles):
    for b in bundles:
        pid = b.profile.profile_id
        assert _load(f"data/profiles/{pid}.json") == b.profile.model_dump(mode="json")
        assert _load(f"data/generated/{pid}.json") == b.generated.model_dump(mode="json")
        assert _load(f"data/seed_plans/{pid}.json") == b.plan.model_dump(mode="json")
        assert _load(f"data/normalized/{pid}.json") == b.unified.model_dump(mode="json")
        assert _load(f"data/validation/{pid}.json")["ok"] is True
