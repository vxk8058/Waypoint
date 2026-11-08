from unittest.mock import Mock

import pytest

from backend.agent.schemas import ProductEvaluation
from backend.agent.subgraphs.checking import build_checking_graph
from backend.services.profile_service import ProfileService


@pytest.fixture
def checking(primary):
    profile = primary.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    worker = Mock()
    balance = sum(a.balance for a in profile.accounts if a.type == "checking")
    worker.with_structured_output.return_value.invoke.return_value = {
        "summary": f"Your checking balance is ${balance}.", "confidence": 0.9,
    }
    return profile, service, worker, build_checking_graph(service, worker)


def invoke(graph, profile):
    return graph.invoke({"query": "What's my checking balance?", "profile_id": profile.profile_id})["result"]


def test_checking_balance_and_trusted_data(checking):
    profile, service, worker, graph = checking
    result = invoke(graph, profile)
    accounts = [a.model_dump(mode="json") for a in profile.accounts if a.type == "checking"]
    assert result.product == "checking" and result.data["accounts"] == accounts
    assert result.data["balance_total"] == sum(a["balance"] for a in accounts)
    assert str(result.data["balance_total"]) in result.summary
    assert result.confidence == 0.9 and result.errors == []
    service.get.assert_called_once_with(profile.profile_id, refresh=False)
    worker.with_structured_output.assert_called_once_with(ProductEvaluation)
    assert "balance_total" not in profile.model_dump()


def test_retrieval_failure_returns_result_without_calling_worker(checking):
    profile, service, worker, graph = checking
    service.get.side_effect = ConnectionError("secret-url-token")
    result = invoke(graph, profile)
    assert result.data == {} and result.confidence == 0
    assert result.errors == ["Checking retrieval failed (ConnectionError)"]
    assert "secret-url-token" not in result.model_dump_json()
    worker.with_structured_output.assert_not_called()


def test_missing_account_does_not_invent_zero_balance(checking):
    profile, _, worker, graph = checking
    profile.accounts = [a for a in profile.accounts if a.type != "checking"]
    result = invoke(graph, profile)
    assert result.data["accounts"] == [] and "balance_total" not in result.data
    assert result.confidence == 0 and "No checking account is available" in result.errors
    worker.with_structured_output.assert_not_called()


def test_stale_synthetic_warnings_cannot_be_erased_by_worker(checking):
    profile, _, _, graph = checking
    profile.data_mode = "pre_seed"
    profile.metadata = {"stale": True, "warnings": ["Fixture source warning"]}
    result = invoke(graph, profile)
    assert result.confidence == 0 and len(result.errors) == 3
    assert "Fixture source warning" in result.errors
    assert result.data["metadata"] == profile.metadata


def test_worker_cannot_replace_facts(checking):
    profile, _, worker, graph = checking
    runner = worker.with_structured_output.return_value
    runner.invoke.return_value = {"summary": "Invented", "confidence": 1, "data": {"balance_total": 999999}}
    result = invoke(graph, profile)
    assert runner.invoke.call_count == 3
    assert result.confidence == 0 and result.errors == ["Checking evaluation failed (RuntimeError)"]
    assert result.data["balance_total"] == sum(a.balance for a in profile.accounts if a.type == "checking")
    assert "Invented" not in result.summary


@pytest.mark.parametrize("invalid", [None, {"summary": "Invalid confidence", "confidence": 2}])
def test_invalid_worker_response_recovers_within_retry_limit(checking, invalid):
    profile, _, worker, graph = checking
    runner = worker.with_structured_output.return_value
    valid = runner.invoke.return_value
    runner.invoke.side_effect = [invalid, valid]
    result = invoke(graph, profile)
    assert runner.invoke.call_count == 2
    assert result.errors == [] and result.confidence == valid["confidence"]
    assert result.summary == valid["summary"]


def test_worker_connection_failure_retains_data_and_source_warnings(checking):
    profile, _, worker, graph = checking
    profile.metadata["warnings"] = ["Some records are unavailable"]
    runner = worker.with_structured_output.return_value
    runner.invoke.side_effect = ConnectionError("private-provider-token")
    result = invoke(graph, profile)
    runner.invoke.assert_called_once()
    assert result.confidence == 0
    assert result.errors == ["Some records are unavailable", "Checking evaluation failed (ConnectionError)"]
    assert result.data["balance_total"] == sum(a.balance for a in profile.accounts if a.type == "checking")
    assert "private-provider-token" not in result.model_dump_json()


def test_failed_refresh_does_not_reuse_previous_invocation_data(checking):
    profile, service, worker, graph = checking
    first = invoke(graph, profile)
    service.get.side_effect = ConnectionError("Refresh failed")
    second = graph.invoke({"query": "Refresh my balance", "profile_id": profile.profile_id,
                           "refresh": True})["result"]
    service.get.assert_called_with(profile.profile_id, refresh=True)
    assert first.data["accounts"]
    assert second.data == {} and second.confidence == 0
    assert second.errors == ["Checking retrieval failed (ConnectionError)"]
    assert worker.with_structured_output.return_value.invoke.call_count == 1
