import httpx
import pytest

from backend.integrations.nessie.client import NessieClient, NessieError
from fake_nessie import FakeNessie


def make(fake=None, **kw):
    fake = fake or FakeNessie()
    return fake, NessieClient("test-key", "https://fake", transport=fake.transport(), sleep=lambda s: None,
                              min_interval=0, **kw)


def test_create_returns_object_with_id():
    fake, c = make()
    obj = c.create("/customers", {"first_name": "A", "last_name": "B", "address": {}})
    assert obj["_id"] in fake.store["customer"]


def test_list_normalizes_id_and_treats_404_as_empty():
    fake, c = make()
    cust = c.create("/customers", {"first_name": "A", "last_name": "B", "address": {}})
    acct = c.create(f"/customers/{cust['_id']}/accounts", {"type": "Checking", "nickname": "n", "rewards": 0, "balance": 5})
    assert c.list(f"/accounts/{acct['_id']}/transfers") == []
    c.create(f"/accounts/{acct['_id']}/transfers", {"transaction_date": "2026-01-01", "status": "completed",
                                                   "amount": 3, "description": "d"})
    rows = c.list(f"/accounts/{acct['_id']}/transfers")
    assert rows[0]["_id"] == rows[0]["id"]


def test_get_retries_on_503_then_succeeds():
    fake, c = make()
    fake.fail("GET", r"^/customers$", 503)
    assert c.get("/customers") == []
    assert fake.requests.count(("GET", "/customers")) == 2


def test_post_is_not_retried_automatically():
    fake, c = make()
    fake.fail("POST", r"^/customers$", 503)
    with pytest.raises(NessieError) as exc:
        c.create("/customers", {"first_name": "A", "last_name": "B", "address": {}})
    assert exc.value.status == 503 and fake.count("customer") == 0


def test_client_error_raises_without_retry():
    fake, c = make()
    with pytest.raises(NessieError) as exc:
        c.get("/nope/x/y/z")
    assert exc.value.status == 403


def test_bad_key_is_reported_and_not_leaked():
    fake = FakeNessie()
    c = NessieClient("wrong-key", "https://fake", transport=fake.transport(), sleep=lambda s: None, min_interval=0)
    with pytest.raises(NessieError) as exc:
        c.get("/customers")
    assert exc.value.status == 401 and "wrong-key" not in str(exc.value)


def test_missing_key_rejected(monkeypatch):
    monkeypatch.delenv("NESSIE_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        NessieClient(api_key="", base_url="https://fake")
