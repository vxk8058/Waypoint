"""Waypoint backend."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_PNC = ROOT / "third_party" / "pnc_wellness"
if str(_PNC) not in sys.path:
    # Make the vendored PNC toolkit importable as `wellness`.
    sys.path.insert(0, str(_PNC))
