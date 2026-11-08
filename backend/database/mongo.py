"""MongoDB persistence for Waypoint application data.

Collections:
- students       one document per profile: PNC-convention profile, generated Nessie-only
                 fields, unified profile and the latest validation report. Unique: profile_id.
- goals          the single primary goal per student. Unique: profile_id.
- seed_plans     latest offline Nessie seed plan per profile. Unique: profile_id.
- nessie_id_map  local_key -> Nessie _id (filled in Phase 3). Unique: (profile_id, local_key);
                 merchants use profile_id "global".
- seed_runs      seed / verify run log (Phase 3). Unique: run_id.

All writes are upserts keyed on unique indexes, so re-running a script never duplicates data.
"""
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from .. import ROOT
from ..config import Settings

COLLECTIONS = ("students", "goals", "seed_plans", "nessie_id_map", "seed_runs")


def get_database(uri: str | None = None, db_name: str | None = None, client: MongoClient | None = None,
                 timeout_ms: int = 10000) -> Database:
    settings = Settings.load()
    if client is None:
        uri = uri or settings.mongodb_uri
        if not uri:
            raise RuntimeError(
                f"MONGODB_URI is not set. Create {ROOT / '.env'} (copy .env.example and fill it in); "
                ".env.example itself is never read and must not contain secrets.")
        if "<" in uri or ">" in uri:
            raise RuntimeError(
                "MONGODB_URI still contains a <placeholder>. Replace <db_password> with the real "
                "password (no angle brackets), URL-encoding special characters, e.g. ',' -> %2C.")
        client =MongoClient(uri, serverSelectionTimeoutMS=timeout_ms, appname="waypoint-backend")
    return client[db_name or settings.mongodb_db]


def explain_connection_error(exc: Exception) -> str:
    """Turn common Atlas connection failures into an actionable hint."""
    text = str(exc)
    if "TLSV1_ALERT_INTERNAL_ERROR" in text or "tlsv1 alert internal error" in text:
        return ("Atlas rejected the TLS handshake. This usually means your IP is not on the cluster's "
                "access list: Atlas > Security > Network Access > Add Current IP Address (or 0.0.0.0/0 "
                "for a demo), wait until it is Active, then retry. Also check the cluster is not paused.")
    if "CERTIFICATE_VERIFY_FAILED" in text:
        return ("Python cannot verify Atlas's TLS certificate. On macOS with python.org Python, run "
                "'Install Certificates.command' from the Python folder in Applications, or pip install certifi.")
    if "Authentication failed" in text or "bad auth" in text:
        return ("Atlas rejected the username/password. Check the database user under Atlas > Security > "
                "Database Access and URL-encode special characters in the password (',' -> %2C).")
    if "DNS" in text or "NXDOMAIN" in text or "nodename nor servname" in text:
        return "The cluster host name could not be resolved. Re-copy the connection string from Atlas."
    return f"Could not reach MongoDB: {text[:300]}"


def check_connection(db: Database) -> None:
    """Ping the server; raise RuntimeError with a readable hint on failure."""
    from pymongo.errors import PyMongoError
    try:
        db.client.admin.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(explain_connection_error(exc)) from exc


def ensure_indexes(db: Database) -> None:
    db.students.create_index([("profile_id", ASCENDING)], unique=True)
    db.goals.create_index([("profile_id", ASCENDING)], unique=True)
    db.seed_plans.create_index([("profile_id", ASCENDING)], unique=True)
    db.nessie_id_map.create_index([("profile_id", ASCENDING), ("local_key", ASCENDING)], unique=True)
    db.nessie_id_map.create_index([("nessie_id", ASCENDING)])
    db.seed_runs.create_index([("run_id", ASCENDING)], unique=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def save_bundle(db: Database, bundle) -> None:
    """Upsert one ProfileBundle (backend.pipeline) into students / goals / seed_plans."""
    pid = bundle.profile.profile_id
    now = _now()
    db.students.update_one({"profile_id": pid}, {
        "$set": {
            "profile_id": pid,
            "persona_key": bundle.profile.persona_key,
            "is_primary_demo": bundle.profile.is_primary_demo,
            "pnc_profile": bundle.profile.model_dump(mode="json"),
            "nessie_generated_fields": bundle.generated.model_dump(mode="json"),
            "unified_profile": bundle.unified.model_dump(mode="json"),
            "validation": bundle.report.model_dump(mode="json"),
            "data_source": "pnc_generated",
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }, upsert=True)
    db.goals.update_one({"profile_id": pid}, {
        "$set": {"profile_id": pid, **bundle.profile.goal.model_dump(mode="json"),
                 "source": "pnc_generated", "updated_at": now},
        "$setOnInsert": {"created_at": now},
    }, upsert=True)
    db.seed_plans.update_one({"profile_id": pid}, {
        "$set": {"profile_id": pid, **bundle.plan.model_dump(mode="json"), "updated_at": now},
        "$setOnInsert": {"created_at": now},
    }, upsert=True)


def load_student(db: Database, profile_id: str) -> dict | None:
    return db.students.find_one({"profile_id": profile_id}, {"_id": 0})


def primary_demo_profile_id(db: Database) -> str | None:
    doc = db.students.find_one({"is_primary_demo": True}, {"profile_id": 1})
    return doc["profile_id"] if doc else None
