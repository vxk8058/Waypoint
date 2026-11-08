from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.agent.graph import build_subgraph_nodes, make_subgraph_node
from backend.agent.schemas import ProductResult, VerifyDecision
from backend.agent.state import initial_state
from backend.agent.subgraphs.other_data import SourceDecision
from backend.auth.users import PublicUser
from backend.services.profile_service import ProfileService


def state_for(profile_id):
    user = PublicUser(user_id=f"user-{profile_id}", profile_id=profile_id, email="demo@example.test",
                      display_name="Demo", first_name="Demo", last_name="User")
    return initial_state("Review my financial records", user)


@pytest.mark.parametrize("retry", [False, True])
def test_wrapper_passes_only_branch_inputs_and_returns_only_result(retry):
    state = state_for("stu-001")
    if retry:
        state["verify"] = VerifyDecision(done=False, need_products=["checking"], missing="Updated balance needed")
    state["final_ui"] = {"private_parent_field": True}
    before = deepcopy(state)
    result = ProductResult(product="checking", summary="Available", confidence=1, data={"balance": 100})
    graph = Mock()
    graph.invoke.return_value = {"result": result, "raw": {"private": True}, "errors": [], "profile_id": "ignored"}
    assert make_subgraph_node(graph)(state) == {"results": [result]}
    graph.invoke.assert_called_once_with({"query": state["query"], "profile_id": "stu-001",
                                         "missing": "Updated balance needed" if retry else "", "refresh": retry})
    assert state == before


@pytest.mark.parametrize("product", ["checking", "savings", "credit_card", "loans", "other_data"])
def test_real_wrappers_keep_profiles_separate_and_forward_feedback(bundles, product):
    profiles = {b.unified.profile_id: b.unified.model_copy(deep=True) for b in bundles}
    for profile in profiles.values():
        profile.data_mode = "nessie"
        profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.side_effect = lambda profile_id, refresh=False: profiles[profile_id]
    selection, evaluation = Mock(), Mock()
    selection.invoke.return_value = {"sources": ["transactions"]}
    evaluation.invoke.return_value = {"summary": "Available records", "confidence": 0.9}
    worker = Mock()
    worker.with_structured_output.side_effect = lambda schema: selection if schema is SourceDecision else evaluation
    nodes = build_subgraph_nodes(service, worker)
    assert set(nodes) == {"checking", "savings", "credit_card", "loans", "other_data"}
    for profile_id in ("stu-001", "stu-002"):
        state = state_for(profile_id)
        state["verify"] = VerifyDecision(done=False, missing="Check current records", need_other_data=True)
        output = nodes[product](state)
        assert set(output) == {"results"} and len(output["results"]) == 1
        result = output["results"][0]
        assert result.product == product
        data = result.data["transactions"] if product == "other_data" else result.data
        assert data["profile_id"] == profile_id
        service.get.assert_called_with(profile_id, refresh=True)
        assert state["results"] == [] and "raw" not in state
    # stu-002 has no card or loans, so those skip evaluation; the first profile still evaluated.
    assert "Check current records" in evaluation.invoke.call_args.args[0]
    if product == "other_data":
        assert "Check current records" in selection.invoke.call_args.args[0]
