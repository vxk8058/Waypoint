from unittest.mock import Mock

import pytest

from backend.agent.subgraphs.savings import build_savings_graph
from backend.services.profile_service import ProfileService


@pytest.fixture
def savings(primary):
    profile = primary.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    worker = Mock()
    worker.with_structured_output.return_value.invoke.return_value = {
        "summary": "Savings and the linked goal are available.", "confidence": 0.9,
    }
    return profile, service, worker, build_savings_graph(service, worker)


def invoke(graph, profile):
    return graph.invoke({"query": "How much is left toward my savings goal?",
                         "profile_id": profile.profile_id})["result"]


@pytest.mark.parametrize("saved,remaining", [(125, 875), (1000, 0), (1200, 0)])
def test_savings_and_goal_use_exact_source_values(savings, saved, remaining):
    profile, _, worker, graph = savings
    profile.goal.target_amount = 1000
    profile.goal.current_saved = saved
    result = invoke(graph, profile)
    accounts = [a.model_dump(mode="json") for a in profile.accounts if a.type == "savings"]
    assert result.product == "savings" and result.data["accounts"] == accounts
    assert result.data["balance_total"] == sum(a["balance"] for a in accounts)
    assert result.data["goal"] == profile.goal.model_dump(mode="json")
    assert result.data["goal_remaining"] == remaining
    assert result.errors == [] and result.confidence == 0.9
    prompt = worker.with_structured_output.return_value.invoke.call_args.args[0]
    assert '"goal_remaining": ' + str(remaining) in prompt
    assert profile.goal.current_saved == saved


def test_unlinked_goal_is_not_invented(savings):
    profile, _, _, graph = savings
    profile.goal.linked_account_id = "different-account"
    result = invoke(graph, profile)
    assert result.data["accounts"] and result.errors == []
    assert "goal" not in result.data and "goal_remaining" not in result.data


def test_missing_savings_does_not_invent_balances_or_goals(savings):
    profile, _, worker, graph = savings
    profile.accounts = [a for a in profile.accounts if a.type != "savings"]
    result = invoke(graph, profile)
    assert result.data["accounts"] == [] and result.confidence == 0
    assert "balance_total" not in result.data and "goal_remaining" not in result.data
    assert result.errors == ["No savings account is available"]
    worker.with_structured_output.assert_not_called()


@pytest.mark.parametrize("failure", ["retrieval", "evaluation"])
def test_failures_keep_savings_identity_and_no_confident_answer(savings, failure):
    profile, service, worker, graph = savings
    if failure == "retrieval":
        service.get.side_effect = ConnectionError("private-token")
    else:
        worker.with_structured_output.return_value.invoke.return_value = None
    result = invoke(graph, profile)
    assert result.product == "savings" and result.confidence == 0
    assert f"Savings {failure} failed" in result.errors[0]
    assert "private-token" not in result.model_dump_json()
    if failure == "retrieval":
        assert result.data == {}
        worker.with_structured_output.assert_not_called()
    else:
        assert result.data["goal"] == profile.goal.model_dump(mode="json")
        assert worker.with_structured_output.return_value.invoke.call_count == 3


def test_savings_warnings_survive_model_evaluation(savings):
    profile, _, _, graph = savings
    profile.data_mode = "pre_seed"
    profile.metadata = {"stale": True, "warnings": ["Source warning"]}
    result = invoke(graph, profile)
    assert result.confidence == 0
    assert result.errors == ["Source warning", "Savings data is a stale snapshot",
                             "Savings data is synthetic pre-seed data, not a live bank balance"]
