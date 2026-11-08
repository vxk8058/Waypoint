"""Shared types: data-origin metadata and money conventions."""
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Origin(str, Enum):
    """Where a value came from.

    - pnc_generated: produced by the PNC-convention synthetic generator (backend.generation).
    - nessie: retrieved from the Nessie API.
    - waypoint_generated: filled in by Waypoint because Nessie requires it and PNC lacks it.
    - derived: calculated from other values (statements, summaries, opening balances).
    """

    PNC_GENERATED = "pnc_generated"
    NESSIE = "nessie"
    WAYPOINT_GENERATED = "waypoint_generated"
    DERIVED = "derived"


class SourceMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin: Origin
    source_id: str | None = None
    note: str | None = None


# Money convention: every amount is a whole-dollar int. The live Nessie API silently
# truncates decimals (verified in Phase 1: balance 500.75 -> 500, deposit 25.75 -> 25),
# so Waypoint never produces cents. Liabilities are stored as positive amounts owed.
Dollars = int
