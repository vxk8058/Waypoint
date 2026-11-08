from unittest.mock import Mock

import pytest

from backend.agent.subgraphs.loans import build_loans_graph
from backend.schemas.student import LOAN_TYPES
from backend.services.profile_service import ProfileService


def setup_graph(bundle):
    profile = bundle.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    worker = Mock()
    worker.with_structured_output.return_value.invoke.return_value = {
        "summary": "The recorded loan balances are available.", "confidence": 0.9,
    }
    return profile, service, worker, build_loans_graph(service, worker)


def invoke(graph, profile):
    return graph.invoke({"query": "What is my loan payoff?", "profile_id": profile.profile_id})["result"]


@pytest.mark.parametrize("profile_id", ["stu-001", "stu-003", "stu-004"])
def test_loan_records_preserved_without_fabricated_payoff(bundles, profile_id):
    bundle = next(b for b in bundles if b.unified.profile_id == profile_id)
    profile, _, worker, graph = setup_graph(bundle)
    result = invoke(graph, profile)
    accounts = [a.model_dump(mode="json") for a in profile.accounts if a.type in LOAN_TYPES]
    ids = {a["account_id"] for a in accounts}
    assert result.product == "loans" and result.data["accounts"] == accounts
    assert result.data["balance_total"] == sum(a["balance"] for a in accounts)
    assert result.data["transactions"] == [t.model_dump(mode="json") for t in profile.transactions
                                            if t.account_id in ids]
    assert result.data["payoff_quote"] is None
    assert "No payoff quote is available" in result.summary
    assert result.errors == [] and result.confidence == 0.9
    assert "goal_remaining" not in result.data
    prompt = worker.with_structured_output.return_value.invoke.call_args.args[0]
    assert '"payoff_quote": null' in prompt and "do not estimate one" in prompt


def test_no_loans_is_not_zero_payoff(bundles):
    bundle = next(b for b in bundles if b.unified.profile_id == "stu-002")
    profile, _, worker, graph = setup_graph(bundle)
    result = invoke(graph, profile)
    assert result.data["accounts"] == [] and "balance_total" not in result.data
    assert result.errors == ["No loan account is available"] and result.confidence == 0
    worker.with_structured_output.assert_not_called()


@pytest.mark.parametrize("failure", ["retrieval", "evaluation"])
def test_loan_failures_preserve_identity_and_facts(primary, failure):
    profile, service, worker, graph = setup_graph(primary)
    if failure == "retrieval":
        service.get.side_effect = ConnectionError("private-token")
    else:
        worker.with_structured_output.return_value.invoke.return_value = {
            "summary": "Invented payoff", "confidence": 1, "data": {"payoff_quote": 999},
        }
    result = invoke(graph, profile)
    assert result.product == "loans" and result.confidence == 0
    assert f"Loans {failure} failed" in result.errors[0]
    assert "private-token" not in result.model_dump_json()
    if failure == "retrieval":
        assert result.data == {}
        worker.with_structured_output.assert_not_called()
    else:
        assert result.data["payoff_quote"] is None and "Invented payoff" not in result.summary
        assert result.data["accounts"]
        assert worker.with_structured_output.return_value.invoke.call_count == 3


def test_loan_warnings_remain_visible(primary):
    profile, _, _, graph = setup_graph(primary)
    profile.data_mode = "pre_seed"
    profile.metadata = {"stale": True, "warnings": ["Source warning"]}
    result = invoke(graph, profile)
    assert result.confidence == 0
    assert result.errors == ["Source warning", "Loans data is a stale snapshot",
                             "Loans data is synthetic pre-seed data, not a live bank balance"]
    assert "No payoff quote is available" in result.summary
