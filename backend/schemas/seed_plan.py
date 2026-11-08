"""A Nessie seed plan: the exact create requests Phase 3 will send, built offline."""
from typing import Literal

from pydantic import BaseModel, Field

from .common import Origin

Resource = Literal["customer", "merchant", "account", "loan", "bill", "deposit", "withdrawal",
                   "purchase", "transfer"]


class SeedOperation(BaseModel):
    local_key: str = Field(description="Stable idempotency key, persisted with the Nessie _id")
    resource: Resource
    parent_key: str | None = Field(None, description="local_key whose Nessie id fills {parent}")
    body: dict
    refs: dict[str, str] = Field(default_factory=dict, description="body field -> local_key to resolve")
    marker: str | None = Field(None, description="[wp:...] tag embedded in nickname/description")
    source_record_id: str | None = None
    source_flow_class: str | None = None
    field_sources: dict[str, Origin] = Field(default_factory=dict)


class SkippedRecord(BaseModel):
    record_id: str
    reason: str


class SeedPlan(BaseModel):
    profile_id: str
    operations: list[SeedOperation]
    skipped: list[SkippedRecord]
    expected_account_balances: dict[str, int] = Field(description="account local_key -> balance in Nessie")
    counts: dict[str, int]
    notes: list[str] = Field(default_factory=list)
