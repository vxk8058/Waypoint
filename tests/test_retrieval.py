import copy

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth import tokens
from backend.config import Settings
from backend.database.mongo import ensure_indexes, get_database, save_bundle
from backend.integrations.nessie.client import NessieClient
from backend.integrations.nessie.gateway import NessieGateway
from backend.mapping.nessie_to_unified import build_unified_from_nessie, clean
from backend.seeding.seeder import Seeder
from backend.services.profile_service import ProfileService
from fake_nessie import FakeNessie


@pytest.fixture(scope="module")
def seeded(bundles):
    """Seed all profiles once; each test gets deep copies of the fake Nessie and database."""
    fake = FakeNessie()
    client = NessieClient("test-key", "https://fake", transport=fake.transport(), sleep=lambda s: None, min_interval=0)
    db = get_database(client=mongomock.MongoClient(), db_name="api_seed")
    ensure_indexes(db)
    seeder = Seeder(client, db)
    for b in bundles:
        save_bundle(db, b)
        assert seeder.seed(b.plan).ok
    docs = {name: list(db[name].find({})) for name in db.list_collection_names()}
    return fake.store, fake.parent, docs


@pytest.fixture()
def world(bundles, seeded):
    store, parent, docs = seeded
    fake = FakeNessie()
    fake.store, fake.parent = copy.deepcopy(store), dict(parent)
    client = NessieClient("test-key", "https://fake", transport=fake.transport(), sleep=lambda s: None, min_interval=0)
    db = get_database(client=mongomock.MongoClient(), db_name="api_test")
    ensure_indexes(db)
    for name, rows in docs.items():
        if rows:
            db[name].insert_many(copy.deepcopy(rows))
    clock = [0.0]
    service = ProfileService(db, NessieGateway(client, max_workers=1), ttl_seconds=60, clock=lambda: clock[0])
    return {"fake": fake, "client": client, "db": db, "service": service, "clock": clock,
            "bundles": {b.profile.profile_id: b for b in bundles}}


def _id_map(db, pid):
    return list(db.nessie_id_map.find({"profile_id": {"$in": [pid, "global"]}}, {"_id": 0}))


def _customer(db, pid):
    return db.nessie_id_map.find_one({"profile_id": pid, "resource": "customer"})["nessie_id"]


# -- Nessie -> unified ---------------------------------------------------------------
def test_nessie_profile_matches_pre_seed(world):
    for pid, b in world["bundles"].items():
        snap = NessieGateway(world["client"]).fetch_customer(_customer(world["db"], pid))
        u = build_unified_from_nessie(b.profile, b.generated, _id_map(world["db"], pid), snap)
        p = b.unified
        assert u.data_mode == "nessie" and not u.metadata["warnings"]
        assert [(a.account_id, a.balance, a.opening_balance) for a in u.accounts] == \
               [(a.account_id, a.balance, a.opening_balance) for a in p.accounts]
        assert u.monthly_summary == p.monthly_summary
        assert u.wellness_inputs == p.wellness_inputs
        key = lambda t: (t.transaction_id, t.date, t.amount, t.balance_change, t.flow_class, t.category, t.description)
        assert [key(t) for t in u.transactions] == [key(t) for t in p.transactions]


def test_sources_and_name_come_from_nessie(world):
    b = world["bundles"]["stu-002"]
    snap = NessieGateway(world["client"]).fetch_customer(_customer(world["db"], "stu-002"))
    u = build_unified_from_nessie(b.profile, b.generated, _id_map(world["db"], "stu-002"), snap)
    assert (u.user.first_name, u.user.last_name) == ("Poyo", "de Avon")
    assert u.user.nessie_customer_id == snap.customer.id
    in_nessie = [t for t in u.transactions if t.nessie_id]
    assert in_nessie and all(t.source.origin.value == "nessie" for t in in_nessie)
    pnc_only = [t for t in u.transactions if not t.nessie_id]
    assert pnc_only and all(t.source.origin.value == "pnc_generated" for t in pnc_only)
    assert all(a.source.origin.value == "nessie" and a.nessie_id for a in u.accounts)


def test_unmapped_nessie_record_is_included_and_inferred(world):
    db, client = world["db"], world["client"]
    b = world["bundles"]["stu-002"]
    checking = db.nessie_id_map.find_one({"profile_id": "stu-002", "local_key": "stu-002:account:stu-002-checking"})
    client.create(f"/accounts/{checking['nessie_id']}/deposits", {"medium": "balance", "transaction_date": "2026-10-30",
                  "status": "completed", "amount": 75, "description": "Birthday money"})
    snap = NessieGateway(client).fetch_customer(_customer(db, "stu-002"))
    u = build_unified_from_nessie(b.profile, b.generated, _id_map(db, "stu-002"), snap)
    extra = [t for t in u.transactions if t.description == "Birthday money"]
    assert len(extra) == 1 and extra[0].flow_class == "income" and "inferred" in extra[0].source.note
    assert u.monthly_summary[-1].income == b.unified.monthly_summary[-1].income + 75


def test_invalid_nessie_record_is_skipped_with_warning(world):
    fake, db = world["fake"], world["db"]
    b = world["bundles"]["stu-002"]
    dep = db.nessie_id_map.find_one({"profile_id": "stu-002", "resource": "deposit"})
    del fake.store["deposit"][dep["nessie_id"]]["amount"]
    snap = NessieGateway(world["client"]).fetch_customer(_customer(db, "stu-002"))
    assert any("skipped invalid deposit" in w for w in snap.warnings)
    u = build_unified_from_nessie(b.profile, b.generated, _id_map(db, "stu-002"), snap)
    assert any("was not returned" in w for w in u.metadata["warnings"])


def test_clean_strips_markers_and_direction():
    assert clean("Credit card payment (out) [wp:stu-001-T00042]") == "Credit card payment"
    assert clean("Student Checking [wp:stu-001:checking]") == "Student Checking"


# -- ProfileService --------------------------------------------------------------------
def test_service_caches_until_ttl(world):
    svc, client, clock = world["service"], world["client"], world["clock"]
    svc.get("stu-002")
    calls = client.calls
    svc.get("stu-002")
    assert client.calls == calls
    clock[0] += 61
    svc.get("stu-002")
    assert client.calls > calls
    calls = client.calls
    svc.get("stu-002", refresh=True)
    assert client.calls > calls


def test_service_serves_stale_snapshot_when_nessie_down(world):
    svc, fake = world["service"], world["fake"]
    fresh = svc.get("stu-002")
    for _ in range(10):
        fake.fail("GET", r"^/customers/", 503)
    stale = svc.get("stu-002", refresh=True)
    assert stale.metadata["stale"] is True and stale.data_mode == "nessie"
    assert any("Nessie unavailable" in w for w in stale.metadata["warnings"])
    assert stale.wellness_inputs == fresh.wellness_inputs


def test_service_pre_seed_when_not_seeded(world):
    db = world["db"]
    db.nessie_id_map.delete_many({"profile_id": "stu-003"})
    p = world["service"].get("stu-003")
    assert p.data_mode == "pre_seed" and "not been seeded" in p.metadata["warnings"][0]


# -- API ---------------------------------------------------------------------------
@pytest.fixture()
def api(world):
    settings = Settings(nessie_api_key="test-key", nessie_base_url="https://fake", mongodb_uri=None,
                        mongodb_db="api_test", session_secret="test-secret", demo_password="pw-123")
    app = create_app(db=world["db"], profiles=world["service"], settings=settings)
    with TestClient(app) as client:
        yield client


def _login(api, password="pw-123"):
    return api.post("/auth/login", json={"email": "poyo@waypoint.demo", "password": password})


def _auth(api):
    return {"Authorization": f"Bearer {_login(api).json()['access_token']}"}


def test_login_links_demo_user_to_stu_002(api):
    r = _login(api)
    assert r.status_code == 200
    assert r.json()["user"]["profile_id"] == "stu-002" and r.json()["user"]["display_name"] == "Poyo de Avon"
    assert _login(api, "wrong").status_code == 401


def test_endpoints_require_auth(api):
    for path in ("/auth/me", "/api/me/profile", "/api/me/accounts", "/api/me/transactions"):
        assert api.get(path).status_code == 401
    assert api.get("/api/me/profile", headers={"Authorization": "Bearer nope.nope"}).status_code == 401


def test_tampered_and_expired_tokens_rejected(api):
    token = _login(api).json()["access_token"]
    payload, sig = token.split(".")
    forged, _ = tokens.issue("other-secret", {"sub": "user-poyo", "profile_id": "stu-001"})
    assert api.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired, _ = tokens.issue("test-secret", {"sub": "user-poyo"}, ttl_seconds=-10)
    assert api.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_profile_endpoint_returns_nessie_backed_stu_002(api, world):
    r = api.get("/api/me/profile", headers=_auth(api))
    assert r.status_code == 200
    body = r.json()
    assert body["profile_id"] == "stu-002" and body["data_mode"] == "nessie"
    assert (body["user"]["first_name"], body["user"]["last_name"]) == ("Poyo", "de Avon")
    assert body["wellness_inputs"] == world["bundles"]["stu-002"].unified.wellness_inputs.model_dump()


def test_transactions_filters_and_pagination(api):
    h = _auth(api)
    all_rows = api.get("/api/me/transactions", params={"limit": 500}, headers=h).json()
    assert all_rows["total"] == 180 and all_rows["data"]["data_mode"] == "nessie"
    dates = [t["date"] for t in all_rows["items"]]
    assert dates == sorted(dates, reverse=True)
    page = api.get("/api/me/transactions", params={"limit": 10, "offset": 10}, headers=h).json()
    assert [t["transaction_id"] for t in page["items"]] == [t["transaction_id"] for t in all_rows["items"][10:20]]
    income = api.get("/api/me/transactions", params={"flow_class": "income", "limit": 500}, headers=h).json()
    assert income["total"] > 0 and all(t["flow_class"] == "income" for t in income["items"])
    oct_rows = api.get("/api/me/transactions", params={"start_date": "2026-10-01", "end_date": "2026-10-31",
                                                      "limit": 500}, headers=h).json()
    assert all(t["date"].startswith("2026-10") for t in oct_rows["items"])
    assert api.get("/api/me/transactions", params={"account_id": "stu-001-checking"}, headers=h).status_code == 404
    assert api.get("/api/me/transactions", params={"start_date": "2026-10-02", "end_date": "2026-10-01"},
                   headers=h).status_code == 422


def test_accounts_bills_goal_summary(api):
    h = _auth(api)
    accounts = api.get("/api/me/accounts", headers=h).json()["accounts"]
    assert {a["type"] for a in accounts} == {"checking", "savings"}
    bills = api.get("/api/me/bills", headers=h).json()
    assert bills["monthly_total"] == 95 + 35 + 25 + 11
    goal = api.get("/api/me/goal", headers=h).json()["goal"]
    assert goal["name"] == "First car fund" and goal["linked_account_id"] == "stu-002-savings"
    summary = api.get("/api/me/summary", headers=h).json()
    assert len(summary["monthly_summary"]) == 6


def test_health(api):
    assert api.get("/health").json()["mongo"] == "ok"


@pytest.mark.parametrize("email,profile_id,name", [
    ("poyo@waypoint.demo", "stu-002", ("Poyo", "de Avon")),
    ("lucas@waypoint.demo", "stu-001", ("Lucas", "Patel")),
    ("leah@waypoint.demo", "stu-003", ("Leah", "Walker")),
    ("priya@waypoint.demo", "stu-004", ("Priya", "Ramirez")),
])
def test_each_demo_login_sees_only_its_student(api, email, profile_id, name):
    r = api.post("/auth/login", json={"email": email, "password": "pw-123"})
    assert r.status_code == 200 and r.json()["user"]["profile_id"] == profile_id
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    profile = api.get("/api/me/profile", headers=h).json()
    assert profile["profile_id"] == profile_id and profile["data_mode"] == "nessie"
    assert (profile["user"]["first_name"], profile["user"]["last_name"]) == name
    assert all(a["account_id"].startswith(profile_id) for a in profile["accounts"])
    other = "stu-001-checking" if profile_id != "stu-001" else "stu-002-checking"
    assert api.get("/api/me/transactions", params={"account_id": other}, headers=h).status_code == 404


def test_demo_login_names_match_nessie_customers(bundles):
    from backend.auth.users import DEMO_USERS
    by_profile = {b.profile.profile_id: b.generated.customer for b in bundles}
    assert {u["profile_id"] for u in DEMO_USERS} == set(by_profile)
    for u in DEMO_USERS:
        c = by_profile[u["profile_id"]]
        assert (u["first_name"], u["last_name"]) == (c.first_name, c.last_name)
