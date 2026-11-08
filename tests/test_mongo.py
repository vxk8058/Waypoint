import mongomock
import pytest
from pymongo.errors import DuplicateKeyError

from backend.database.mongo import ensure_indexes, get_database, primary_demo_profile_id, save_bundle


@pytest.fixture()
def db():
    database = get_database(client=mongomock.MongoClient(), db_name="waypoint_test")
    ensure_indexes(database)
    return database


def test_save_is_idempotent(db, bundles):
    for _ in range(2):
        for b in bundles:
            save_bundle(db, b)
    assert db.students.count_documents({}) == len(bundles)
    assert db.goals.count_documents({}) == len(bundles)
    assert db.seed_plans.count_documents({}) == len(bundles)


def test_one_goal_per_student(db, primary):
    save_bundle(db, primary)
    with pytest.raises(DuplicateKeyError):
        db.goals.insert_one({"profile_id": primary.profile.profile_id, "name": "second goal"})


def test_primary_demo_lookup(db, bundles):
    for b in bundles:
        save_bundle(db, b)
    assert primary_demo_profile_id(db) == "stu-001"


def test_nessie_id_map_unique(db):
    db.nessie_id_map.insert_one({"profile_id": "stu-001", "local_key": "k", "nessie_id": "a"})
    with pytest.raises(DuplicateKeyError):
        db.nessie_id_map.insert_one({"profile_id": "stu-001", "local_key": "k", "nessie_id": "b"})


def test_missing_uri_points_to_env_file(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with pytest.raises(RuntimeError, match=r"\.env"):
        get_database(uri="")


def test_placeholder_uri_rejected():
    with pytest.raises(RuntimeError, match="placeholder"):
        get_database(uri="mongodb+srv://user:<db_password>@cluster0.example.mongodb.net/")
