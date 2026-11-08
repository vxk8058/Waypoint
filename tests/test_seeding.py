import mongomock
import pytest

from backend.database.mongo import ensure_indexes, get_database
from backend.integrations.nessie.client import NessieClient
from backend.seeding.seeder import Seeder
from backend.seeding.verifier import verify_profile
from fake_nessie import FakeNessie


@pytest.fixture()
def env():
    fake = FakeNessie()
    client = NessieClient("test-key", "https://fake", transport=fake.transport(), sleep=lambda s: None, min_interval=0)
    db = get_database(client=mongomock.MongoClient(), db_name="seed_test")
    ensure_indexes(db)
    return fake, client, db


def total_records(fake):
    return sum(len(v) for v in fake.store.values())


def test_seed_creates_everything_and_verifies(env, primary):
    fake, client, db = env
    result = Seeder(client, db).seed(primary.plan)
    assert result.ok and result.created == len(primary.plan.operations)
    report = verify_profile(primary.profile, primary.plan, client, db)
    assert report.ok, (report.missing, report.mismatches, report.unexpected)
    assert all(a.nessie_balance == a.expected_balance for a in report.accounts)


def test_reseed_is_idempotent(env, primary):
    fake, client, db = env
    Seeder(client, db).seed(primary.plan)
    before = total_records(fake)
    again = Seeder(client, db).seed(primary.plan)
    assert again.created == 0 and again.existing == len(primary.plan.operations)
    assert total_records(fake) == before


def test_lost_id_map_is_rebuilt_by_marker_without_duplicates(env, primary):
    fake, client, db = env
    Seeder(client, db).seed(primary.plan)
    before = total_records(fake)
    db.nessie_id_map.delete_many({})  # e.g. a different MongoDB (Atlas vs local)
    result = Seeder(client, db).seed(primary.plan)
    assert result.created == 0 and result.adopted == len(primary.plan.operations)
    assert total_records(fake) == before
    assert verify_profile(primary.profile, primary.plan, client, db).ok


def test_crash_mid_run_resumes(env, primary):
    fake, client, db = env
    fake.fail("POST", r"/purchases$", 400)  # a hard rejection stops the run
    first = Seeder(client, db).seed(primary.plan)
    assert not first.ok and first.created > 0
    second = Seeder(client, db).seed(primary.plan)
    assert second.ok and second.created + second.existing == len(primary.plan.operations)
    assert verify_profile(primary.profile, primary.plan, client, db).ok


def test_ambiguous_post_failure_adopts_instead_of_duplicating(env, primary):
    fake, client, db = env
    fake.fail("POST", r"/deposits$", 504, apply_effect=True)  # server wrote it, client saw 504
    result = Seeder(client, db).seed(primary.plan)
    assert result.ok and result.adopted == 1
    report = verify_profile(primary.profile, primary.plan, client, db)
    assert report.ok and not report.unexpected


def test_revalidate_recreates_records_deleted_in_nessie(env, primary):
    fake, client, db = env
    Seeder(client, db).seed(primary.plan)
    victim = db.nessie_id_map.find_one({"resource": "deposit"})
    fake.store["deposit"].pop(victim["nessie_id"])
    assert not verify_profile(primary.profile, primary.plan, client, db).ok
    result = Seeder(client, db, revalidate=True).seed(primary.plan)
    assert result.created == 1
    assert verify_profile(primary.profile, primary.plan, client, db).ok


def test_verify_detects_tampering(env, primary):
    fake, client, db = env
    Seeder(client, db).seed(primary.plan)
    acct = db.nessie_id_map.find_one({"resource": "account"})
    fake.store["account"][acct["nessie_id"]]["balance"] += 1
    report = verify_profile(primary.profile, primary.plan, client, db)
    assert not report.ok and any(m["field"] == "balance" for m in report.mismatches)


def test_reset_removes_accounts_and_children_but_keeps_customer(env, primary):
    fake, client, db = env
    seeder = Seeder(client, db)
    seeder.seed(primary.plan)
    out = seeder.reset(primary.profile.profile_id)
    assert out["deleted"]["account"] == 3
    for kind in ("account", "deposit", "withdrawal", "purchase", "transfer", "bill", "loan"):
        assert fake.count(kind) == 0
    assert fake.count("customer") == 1 and fake.count("merchant") > 0
    again = seeder.seed(primary.plan)
    assert again.ok and again.existing == 1 + len(primary.profile.merchants)  # customer + merchants reused
    assert verify_profile(primary.profile, primary.plan, client, db).ok


def test_merchants_shared_across_profiles(env, bundles):
    fake, client, db = env
    seeder = Seeder(client, db)
    for b in bundles:
        assert seeder.seed(b.plan).ok
    unique = {m.merchant_key for b in bundles for m in b.profile.merchants}
    assert fake.count("merchant") == len(unique)
    assert fake.count("customer") == len(bundles)
