"""Single entry point for a student's unified financial profile.

Retrieval order:
1. In-memory cache (TTL) - so endpoints and calculations never call Nessie repeatedly.
2. Live Nessie fetch (one pass via NessieGateway) merged with PNC-only data from MongoDB;
   the result is saved to `profile_snapshots`.
3. If Nessie fails: the last snapshot, flagged metadata.stale = True.
4. If the profile was never seeded (or Nessie is not configured): the pre-seed profile
   stored in MongoDB, flagged data_mode = "pre_seed".
"""
import logging
import threading
import time
from datetime import datetime, timezone

import httpx
from pymongo.database import Database

from ..integrations.nessie.client import NessieError
from ..integrations.nessie.gateway import NessieGateway
from ..mapping.missing_fields import GeneratedFields
from ..mapping.nessie_to_unified import build_unified_from_nessie
from ..schemas.normalized import UnifiedProfile
from ..schemas.student import StudentProfile

log = logging.getLogger("waypoint.profile")


class ProfileNotFound(Exception):
    pass


class ProfileService:
    def __init__(self, db: Database, gateway: NessieGateway | None, ttl_seconds: int = 300, clock=time.monotonic):
        self.db, self.gateway, self.ttl, self.clock = db, gateway, ttl_seconds, clock
        self._cache: dict[str, tuple[float, UnifiedProfile]] = {}
        self._lock = threading.Lock()

    def invalidate(self, profile_id: str | None = None):
        with self._lock:
            if profile_id:
                self._cache.pop(profile_id, None)
            else:
                self._cache.clear()

    def get(self, profile_id: str, refresh: bool = False) -> UnifiedProfile:
        with self._lock:
            hit = self._cache.get(profile_id)
        if hit and not refresh and self.clock() - hit[0] < self.ttl:
            return hit[1]
        profile = self._load(profile_id)
        with self._lock:
            self._cache[profile_id] = (self.clock(), profile)
        return profile

    def _load(self, profile_id: str) -> UnifiedProfile:
        student = self.db.students.find_one({"profile_id": profile_id})
        if not student:
            raise ProfileNotFound(profile_id)
        customer = self.db.nessie_id_map.find_one({"profile_id": profile_id, "resource": "customer"})
        if self.gateway is None or customer is None:
            reason = "Nessie is not configured" if self.gateway is None else "profile has not been seeded into Nessie"
            return self._pre_seed(student, reason)
        try:
            snap = self.gateway.fetch_customer(customer["nessie_id"])
            id_map = list(self.db.nessie_id_map.find({"profile_id": {"$in": [profile_id, "global"]}}, {"_id": 0}))
            unified = build_unified_from_nessie(
                StudentProfile.model_validate(student["pnc_profile"]),
                GeneratedFields.model_validate(student["nessie_generated_fields"]), id_map, snap)
        except (NessieError, httpx.HTTPError) as exc:
            log.warning("Nessie fetch failed for %s: %s", profile_id, exc)
            return self._fallback(student, f"Nessie unavailable: {exc}")
        self.db.profile_snapshots.update_one({"profile_id": profile_id}, {"$set": {
            "profile_id": profile_id, "unified_profile": unified.model_dump(mode="json"),
            "saved_at": datetime.now(timezone.utc)}}, upsert=True)
        return unified

    def _fallback(self, student: dict, reason: str) -> UnifiedProfile:
        snap = self.db.profile_snapshots.find_one({"profile_id": student["profile_id"]})
        if snap:
            unified = UnifiedProfile.model_validate(snap["unified_profile"])
            meta = {**unified.metadata, "stale": True, "snapshot_saved_at": snap["saved_at"].isoformat()
                    if hasattr(snap["saved_at"], "isoformat") else str(snap["saved_at"]),
                    "warnings": [*unified.metadata.get("warnings", []), reason + "; serving last snapshot"]}
            return unified.model_copy(update={"metadata": meta})
        return self._pre_seed(student, reason + "; no snapshot available")

    @staticmethod
    def _pre_seed(student: dict, reason: str) -> UnifiedProfile:
        unified = UnifiedProfile.model_validate(student["unified_profile"])
        meta = {**unified.metadata, "stale": False, "warnings": [reason + "; serving pre-seed profile"]}
        return unified.model_copy(update={"metadata": meta})
