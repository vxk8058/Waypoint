from unittest.mock import Mock

import pytest

from backend.agent.subgraphs.credit_card import build_credit_card_graph
from backend.services.profile_service import ProfileService


def setup_graph(bundle):
    profile = bundle.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    worker = Mock()
    worker.with_structured_output.return_value.invoke.return_value = {
        "summary": "The credit card records are available.", "confidence": 0.9,
    }
    return profile, service, worker, build_credit_card_graph(service, worker)


def invoke(graph, profile):
    return graph.invoke({"query": "What is my credit card balance?",
                         "profile_id": profile.profile_id})["result"]


@pytest.mark.parametrize("profile_id", ["stu-001", "stu-003", "stu-004"])
def test_cards_preserve_balances_limits_and_transactions(bundles, profile_id):
    bundle = next(b for b in bundles if b.unified.profile_id == profile_id)
    profile, _, worker, graph = setup_graph(bundle)
    result = invoke(graph, profile)
    accounts = [a.model_dump(mode="json") for a in profile.accounts if a.type == "credit_card"]
    ids = {a["account_id"] for a in accounts}
    assert result.product == "credit_card" and result.data["accounts"] == accounts
    assert result.data["balance_total"] == sum(a["balance"] for a in accounts)
    assert result.data["transactions"] == [t.model_dump(mode="json") for t in profile.transactions
                                            if t.account_id in ids]
    assert result.errors == [] and result.confidence == 0.9
    assert "goal" not in result.data and "goal_remaining" not in result.data
    prompt = worker.with_structured_output.return_value.invoke.call_args.args[0]
    assert "amounts owed, not spendable cash" in prompt


def test_profile_without_card_does_not_become_zero_debt(bundles):
    bundle = next(b for b in bundles if b.unified.profile_id == "stu-002")
    profile, _, worker, graph = setup_graph(bundle)
    result = invoke(graph, profile)
    assert result.data["accounts"] == [] and "balance_total" not in result.data
    assert result.errors == ["No credit card account is available"]
    assert result.confidence == 0
    worker.with_structured_output.assert_not_called()


@pytest.mark.parametrize("failure", ["retrieval", "evaluation"])
def test_card_failure_preserves_identity_and_errors(primary, failure):
    profile, service, worker, graph = setup_graph(primary)
    if failure == "retrieval":
        service.get.side_effect = ConnectionError("private-token")
    else:
        worker.with_structured_output.return_value.invoke.return_value = {
            "summary": "Invented", "confidence": 1, "data": {"balance_total": 999999},
        }
    result = invoke(graph, profile)
    assert result.product == "credit_card" and result.confidence == 0
    assert f"Credit card {failure} failed" in result.errors[0]
    assert "private-token" not in result.model_dump_json()
    if failure == "retrieval":
        assert result.data == {}
        worker.with_structured_output.assert_not_called()
    else:
        assert result.data["balance_total"] == sum(a.balance for a in profile.accounts if a.type == "credit_card")
        assert worker.with_structured_output.return_value.invoke.call_count == 3
        assert "Invented" not in result.summary


def test_card_source_warnings_cannot_be_erased(primary):
    profile, _, _, graph = setup_graph(primary)
    profile.data_mode = "pre_seed"
    profile.metadata = {"stale": True, "warnings": ["Source warning"]}
    result = invoke(graph, profile)
    assert result.confidence == 0
    assert result.errors == ["Source warning", "Credit card data is a stale snapshot",
                             "Credit card data is synthetic pre-seed data, not a live bank balance"]
