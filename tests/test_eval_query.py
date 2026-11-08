from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.agent.nodes.eval_query import eval_query, route_to_products
from backend.agent.schemas import RouteDecision, VerifyDecision


@pytest.mark.parametrize("query,products", [
    ("What's my checking balance?", ["checking"]),
    ("Compare my savings with my loans", ["savings", "loans"]),
])
def test_initial_routing_returns_validated_products_without_identity_data(query, products):
    state = {"query": query, "profile_id": "private-profile", "user_id": "private-user", "results": []}
    planner = Mock()
    runner = planner.with_structured_output.return_value
    runner.invoke.return_value = {"products": products, "reasoning": "Needed products"}
    before = deepcopy(state)
    update = eval_query(state, planner)
    assert set(update) == {"route"}
    assert route_to_products({**state, **update}) == products
    planner.with_structured_output.assert_called_once_with(RouteDecision)
    assert "private-profile" not in runner.invoke.call_args.args[0]
    assert "private-user" not in runner.invoke.call_args.args[0]
    assert state == before


@pytest.mark.parametrize("query", ["Help me with my money", "Transfer $50", "What's the weather?"])
def test_no_match_preserves_explanation_without_defaulting_to_checking(query):
    planner = Mock()
    planner.with_structured_output.return_value.invoke.return_value = {
        "products": [], "reasoning": "Please specify a supported banking data question.",
    }
    state = {"query": query}
    update = eval_query(state, planner)
    assert update["route"].products == [] and not update["verify"].done
    assert update["verify"].missing == update["route"].reasoning
    assert route_to_products({**state, **update}) == ["gen_ui"]


@pytest.mark.parametrize("bad", [None, {"products": ["unknown"], "reasoning": "Invalid"}])
def test_invalid_output_exhaustion_stops_without_fetching(bad):
    planner = Mock()
    runner = planner.with_structured_output.return_value
    runner.invoke.return_value = bad
    update = eval_query({"query": "Balance?"}, planner)
    assert runner.invoke.call_count == 3
    assert update["verify"].missing == "Query routing is unavailable (RuntimeError)."
    assert route_to_products(update) == ["gen_ui"]


def test_invalid_output_can_recover():
    planner = Mock()
    runner = planner.with_structured_output.return_value
    runner.invoke.side_effect = [None, {"products": ["checking"], "reasoning": "Checking balance"}]
    update = eval_query({"query": "Checking balance?"}, planner)
    assert runner.invoke.call_count == 2 and route_to_products(update) == ["checking"]


@pytest.mark.parametrize("products,other,expected", [
    (["savings", "loans"], False, ["savings", "loans"]),
    ([], True, ["other_data"]),
    (["checking"], True, ["checking", "other_data"]),
    ([], False, ["gen_ui"]),
])
def test_verification_targets_bypass_reclassification(products, other, expected):
    planner = Mock()
    state = {"query": "Original question", "route": RouteDecision(products=["credit_card"], reasoning="Old route"),
             "verify": VerifyDecision(done=False, need_products=products,
                                      need_other_data=other, missing="Need updated facts")}
    update = eval_query(state, planner)
    assert update["route"].products == products
    assert update["route"].reasoning == "Need updated facts"
    assert route_to_products({**state, **update}) == expected
    planner.with_structured_output.assert_not_called()


def test_verified_question_does_not_fetch_again():
    planner = Mock()
    state = {"verify": VerifyDecision(done=True)}
    update = eval_query(state, planner)
    assert route_to_products({**state, **update}) == ["gen_ui"]
    planner.with_structured_output.assert_not_called()


def test_provider_error_does_not_leak_details():
    planner = Mock()
    runner = planner.with_structured_output.return_value
    runner.invoke.side_effect = ConnectionError("private-provider-token")
    update = eval_query({"query": "Balance?"}, planner)
    runner.invoke.assert_called_once()
    assert update["verify"].missing == "Query routing is unavailable (ConnectionError)."
