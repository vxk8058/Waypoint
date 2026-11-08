"""Idempotent Nessie seeding from an offline SeedPlan.

For each plan operation, in order:
1. If `nessie_id_map` already has the local_key -> reuse it ("existing").
   With revalidate=True the id is first checked with GET; a 404 drops the stale mapping.
2. Else look for a record in Nessie carrying the operation's [wp:...] marker (or, for
   customers/merchants, identical identifying fields) -> adopt it ("adopted").
3. Else create it ("created"). The id is persisted immediately, so a crash mid-run is
   resumable and never duplicates records.

Merchants are global in Nessie and cannot be deleted, so they are mapped under
profile_id "global" and shared by all profiles.

Never called by simulations: hypothetical scenarios must not touch Nessie.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pymongo.database import Database

from ..integrations.nessie.client import NessieClient, NessieError
from ..integrations.nessie.resources import ACCOUNT_CHILDREN, DELETABLE, ITEM_PATHS, LIST_PATHS, MARKER_FIELDS
from ..schemas.nessie import CREATE_PATHS, REF_PREFIX
from ..schemas.seed_plan import SeedOperation, SeedPlan

GLOBAL = "global"
# Resources Nessie can update in place with PUT (they cannot be deleted, so updating is the
# only way to apply plan changes such as a renamed customer).
UPDATABLE = {"customer": ("first_name", "last_name", "address"), "merchant": ("name", "category", "address", "geocode")}
MARKER_RE = re.compile(r"\[wp:[^\]]+\]")


def _now():
    return datetime.now(timezone.utc)


def body_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]


def map_scope(profile_id: str, op: SeedOperation) -> str:
    return GLOBAL if op.resource == "merchant" else profile_id


def find_marker(record: dict, resource: str) -> str | None:
    text = record.get(MARKER_FIELDS.get(resource, ""), "") or ""
    m = MARKER_RE.search(text)
    return m.group(0) if m else None


def _same_address(a: dict | None, b: dict) -> bool:
    a = a or {}
    return all(str(a.get(k, "")) == str(b.get(k, "")) for k in ("street_number", "street_name", "city", "state", "zip"))


def matches(op: SeedOperation, record: dict) -> bool:
    """Does an existing Nessie record correspond to this plan operation?"""
    if op.resource == "customer":
        return (record.get("first_name") == op.body["first_name"] and record.get("last_name") == op.body["last_name"]
                and _same_address(record.get("address"), op.body["address"]))
    if op.resource == "merchant":
        return (record.get("name") == op.body["name"] and record.get("category") == op.body["category"]
                and _same_address(record.get("address"), op.body["address"]))
    return op.marker is not None and find_marker(record, op.resource) == op.marker


@dataclass
class SeedResult:
    profile_id: str
    created: int = 0
    adopted: int = 0
    existing: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    by_resource: dict = field(default_factory=dict)

    def bump(self, resource: str, outcome: str):
        setattr(self, outcome, getattr(self, outcome) + 1)
        self.by_resource.setdefault(resource, {}).setdefault(outcome, 0)
        self.by_resource[resource][outcome] += 1

    @property
    def ok(self) -> bool:
        return self.failed == 0


class Seeder:
    def __init__(self, client: NessieClient, db: Database, *, revalidate: bool = False):
        self.client, self.db, self.revalidate = client, db, revalidate
        self._lists: dict[tuple[str, str], list[dict]] = {}

    # -- id map ---------------------------------------------------------------
    def mapped(self, scope: str, local_key: str) -> dict | None:
        return self.db.nessie_id_map.find_one({"profile_id": scope, "local_key": local_key})

    def nessie_id(self, scope: str, local_key: str) -> str:
        doc = self.mapped(scope, local_key)
        if doc is None:
            raise KeyError(f"no Nessie id for {local_key}")
        return doc["nessie_id"]

    def _record(self, scope: str, op: SeedOperation, nessie_id: str, parent_id: str | None, status: str):
        now = _now()
        self.db.nessie_id_map.update_one({"profile_id": scope, "local_key": op.local_key}, {
            "$set": {"profile_id": scope, "local_key": op.local_key, "resource": op.resource,
                     "nessie_id": nessie_id, "parent_key": op.parent_key, "parent_nessie_id": parent_id,
                     "marker": op.marker, "source_record_id": op.source_record_id,
                     "body_hash": body_hash(op.body), "status": status, "updated_at": now},
            "$setOnInsert": {"created_at": now}}, upsert=True)

    # -- Nessie lookups -------------------------------------------------------
    def _listing(self, resource: str, parent_id: str | None, refresh: bool = False) -> list[dict]:
        key = (resource, parent_id or "")
        if refresh or key not in self._lists:
            self._lists[key] = self.client.list(LIST_PATHS[resource].format(parent=parent_id))
        return self._lists[key]

    def _find_existing(self, op: SeedOperation, parent_id: str | None, refresh=False,
                       profile_id: str | None = None) -> list[dict]:
        rows = self._listing(op.resource, parent_id, refresh)
        found = [r for r in rows if matches(op, r)]
        if not found and op.resource == "customer" and profile_id:
            # Renamed customer: same address and owns this profile's marker-tagged accounts.
            prefix = f"[wp:{profile_id}:"
            for r in rows:
                if _same_address(r.get("address"), op.body["address"]) and any(
                        (find_marker(a, "account") or "").startswith(prefix)
                        for a in self.client.list(LIST_PATHS["account"].format(parent=r["_id"]))):
                    found.append(r)
        return found

    def _apply_update(self, op: SeedOperation, nessie_id: str, record: dict | None, result: SeedResult) -> bool:
        """PUT changed fields for updatable resources. Returns True if an update was sent."""
        fields = UPDATABLE.get(op.resource)
        if not fields:
            return False
        if record is not None and all(
                (_same_address(record.get(f), op.body[f]) if f == "address" else record.get(f) == op.body[f])
                for f in fields):
            return False
        self.client.update(ITEM_PATHS[op.resource].format(id=nessie_id), {f: op.body[f] for f in fields})
        result.updated += 1
        return True

    def _resolve_body(self, profile_id: str, op: SeedOperation) -> dict:
        body = dict(op.body)
        for field_name, ref in op.refs.items():
            scope = GLOBAL if ref.startswith("merchant:") else profile_id
            body[field_name] = self.nessie_id(scope, ref)
            assert op.body[field_name] == REF_PREFIX + ref
        return body

    # -- seeding --------------------------------------------------------------
    def seed(self, plan: SeedPlan, stop_on_error: bool = True, progress=None) -> SeedResult:
        result = SeedResult(profile_id=plan.profile_id)
        for i, op in enumerate(plan.operations, start=1):
            try:
                self._seed_one(plan.profile_id, op, result)
            except (NessieError, KeyError) as exc:
                result.failed += 1
                result.errors.append({"local_key": op.local_key, "resource": op.resource, "error": str(exc)})
                if stop_on_error:
                    break
            if progress and (i % 25 == 0 or i == len(plan.operations)):
                progress(i, len(plan.operations), result)
        return result

    def _seed_one(self, profile_id: str, op: SeedOperation, result: SeedResult):
        scope = map_scope(profile_id, op)
        parent_id = self.nessie_id(profile_id, op.parent_key) if op.parent_key else None

        existing = self.mapped(scope, op.local_key)
        if existing:
            if not self.revalidate or self.client.get_or_none(ITEM_PATHS[op.resource].format(id=existing["nessie_id"])):
                if existing.get("body_hash") != body_hash(op.body):
                    if self._apply_update(op, existing["nessie_id"], None, result):
                        self._record(scope, op, existing["nessie_id"], parent_id, existing.get("status", "created"))
                    else:
                        result.warnings.append({"local_key": op.local_key,
                                                "warning": "plan changed since this record was seeded; use --reset to recreate"})
                result.bump(op.resource, "existing")
                return
            self.db.nessie_id_map.delete_one({"_id": existing["_id"]})

        found = self._find_existing(op, parent_id, profile_id=profile_id)
        if found:
            if len(found) > 1:
                result.warnings.append({"local_key": op.local_key,
                                        "warning": f"{len(found)} matching records in Nessie; adopted the first"})
            self._apply_update(op, found[0]["_id"], found[0], result)
            self._record(scope, op, found[0]["_id"], parent_id, "adopted")
            result.bump(op.resource, "adopted")
            return

        body = self._resolve_body(profile_id, op)
        path = CREATE_PATHS[op.resource].format(parent=parent_id)
        try:
            created = self.client.create(path, body)
        except NessieError as exc:
            if exc.status is not None and exc.status < 500 and exc.status != 429:
                raise  # a real rejection (e.g. 400) - do not retry
            # The POST may have succeeded server-side: check by marker before one retry.
            found = self._find_existing(op, parent_id, refresh=True)
            if found:
                self._record(scope, op, found[0]["_id"], parent_id, "adopted")
                result.bump(op.resource, "adopted")
                return
            created = self.client.create(path, body)
        self._record(scope, op, created["_id"], parent_id, "created")
        self._listing(op.resource, parent_id).append(created)
        result.bump(op.resource, "created")

    # -- reset ----------------------------------------------------------------
    def reset(self, profile_id: str) -> dict:
        """Delete this profile's accounts and everything under them, then clear their mappings.

        Customers and merchants cannot be deleted in Nessie; they stay mapped and are reused.
        Nessie does not cascade account deletes, so children are deleted first: every record
        under the profile's accounts that carries this profile's marker, plus mapped records.
        """
        counts = {r: 0 for r in DELETABLE}
        deleted: set[str] = set()

        def delete(resource: str, nessie_id: str):
            if nessie_id in deleted:
                return
            deleted.add(nessie_id)
            counts[resource] += self.client.delete(ITEM_PATHS[resource].format(id=nessie_id))

        accounts = list(self.db.nessie_id_map.find({"profile_id": profile_id, "resource": "account"}))
        prefix = f"[wp:{profile_id}"
        for acct in accounts:
            for resource in ACCOUNT_CHILDREN:
                for rec in self.client.list(LIST_PATHS[resource].format(parent=acct["nessie_id"])):
                    marker = find_marker(rec, resource) or ""
                    if marker.startswith(prefix):
                        delete(resource, rec["_id"])
        for doc in self.db.nessie_id_map.find({"profile_id": profile_id, "resource": {"$in": list(DELETABLE)}}):
            if doc["resource"] != "account":
                delete(doc["resource"], doc["nessie_id"])
        for acct in accounts:
            delete("account", acct["nessie_id"])
        removed = self.db.nessie_id_map.delete_many({"profile_id": profile_id, "resource": {"$in": list(DELETABLE)}})
        self._lists.clear()
        return {"deleted": counts, "mappings_removed": removed.deleted_count}
