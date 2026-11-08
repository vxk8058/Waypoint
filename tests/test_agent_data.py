from unittest.mock import Mock

import mongomock
import pytest

from backend.agent.data import get_data
from backend.services.profile_service import ProfileNotFound, ProfileService


@pytest.fixture
def profiles(bundles):
    db = mongomock.MongoClient().agent_test
    for bundle in bundles:
        db.students.insert_one({"profile_id": bundle.unified.profile_id,
                                "unified_profile": bundle.unified.model_dump(mode="json")})
    return ProfileService(db, gateway=None)


@pytest.mark.parametrize("source,types", [
    ("checking", {"checking"}), ("savings", {"savings"}),
    ("credit_card", {"credit_card"}), ("loans", {"student_loan", "auto_loan"}),
])
def test_product_data_matches_existing_fixtures(profiles, bundles, source, types):
    for bundle in bundles:
        original = bundle.unified.model_dump(mode="json")
        data = get_data(profiles, bundle.unified.profile_id, source)
        expected = [a for a in original["accounts"] if a["type"] in types]
        ids = {a["account_id"] for a in expected}
        assert data["accounts"] == expected
        assert data["transactions"] == [t for t in original["transactions"] if t["account_id"] in ids]
        assert data["bills"] == [b for b in original["bills"] if b["account_id"] in ids]
        assert data["as_of_date"] == original["as_of_date"]
        assert data["data_mode"] == "pre_seed"
        assert "pre-seed" in data["metadata"]["warnings"][0]
        assert all(type(a["balance"]) is int for a in data["accounts"])
        assert "user" not in data and "pnc_view" not in data


@pytest.mark.parametrize("source", ["credit_card", "loans"])
def test_absent_accounts_are_empty_not_zero_balances(profiles, source):
    data = get_data(profiles, "stu-002", source)
    assert data["accounts"] == data["transactions"] == data["bills"] == []
    assert "balance" not in data


def test_other_sources_and_savings_goal(profiles, primary):
    profile = primary.unified.model_dump(mode="json")
    assert get_data(profiles, profile["profile_id"], "transactions")["transactions"] == profile["transactions"]
    bio = get_data(profiles, profile["profile_id"], "bio")
    assert bio["student"] == profile["user"]["student"]
    assert "address" not in bio and "user" not in bio
    assert get_data(profiles, profile["profile_id"], "savings")["goal"] == profile["goal"]


def test_stale_warnings_and_refresh_survive_boundary(primary):
    service = Mock(spec=ProfileService)
    profile = primary.unified.model_copy(deep=True)
    profile.metadata.update(stale=True, warnings=["API unavailable; serving last snapshot"])
    service.get.return_value = profile
    data = get_data(service, profile.profile_id, "checking", refresh=True)
    service.get.assert_called_once_with(profile.profile_id, refresh=True)
    assert data["metadata"] == profile.metadata
    data["metadata"]["warnings"].append("local change")
    data["accounts"][0]["balance"] = 0
    assert profile.metadata["warnings"] == ["API unavailable; serving last snapshot"]
    assert profile.accounts[0].balance != 0


def test_missing_profile_and_retrieval_failure_propagate(profiles):
    with pytest.raises(ProfileNotFound):
        get_data(profiles, "missing", "checking")
    service = Mock(spec=ProfileService)
    service.get.side_effect = ConnectionError("Fixture retrieval failed")
    with pytest.raises(ConnectionError, match="Fixture retrieval failed"):
        get_data(service, "stu-001", "checking")


def test_wrong_profile_is_rejected(primary):
    service = Mock(spec=ProfileService)
    service.get.return_value = primary.unified
    with pytest.raises(ValueError, match="does not match"):
        get_data(service, "stu-002", "checking")


@pytest.mark.parametrize("source,error", [("unknown", ValueError), ("other_api", NotImplementedError)])
def test_unavailable_sources_do_not_fetch(source, error):
    service = Mock(spec=ProfileService)
    with pytest.raises(error):
        get_data(service, "stu-001", source)
    service.get.assert_not_called()
