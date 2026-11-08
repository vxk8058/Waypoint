from unittest.mock import Mock

import pytest

from backend.agent.nodes.eval_query import eval_query, route_to_products
from backend.agent.nodes.verify import MAX_ITERATIONS, after_verify, verify
from backend.agent.schemas import ProductResult, RouteDecision

RESULT = ProductResult(product="checking", data={"balance_total": 1234, "metadata": {"stale": True}},
                       errors=["Checking data is a stale snapshot"], summary="Balance is $1,234.", confidence=0)


def planner_returning(*outputs):
    planner = Mock()
    planner.with_structured_output.return_value.invoke.side_effect = list(outputs)
    return planner


def state(**extra):
    return {"query": "What's my checking balance?", "profile_id": "private-profile",
            "results": [RESULT], "iterations": 0, **extra}


def test_prompt_includes_trusted_data_errors_and_freshness_but_not_identity():
    planner = planner_returning({"done": True})
    update = verify(state(), planner)
    prompt = planner.with_structured_output.return_value.invoke.call_args.args[0]
    assert '"balance_total": 1234' in prompt and '"stale": true' in prompt and "stale snapshot" in prompt
    assert "private-profile" not in prompt
    assert update["iterations"] == 1 and update["verify"].done
    assert after_verify(update) == "gen_ui"


@pytest.mark.parametrize("decision,expected", [
    ({"done": False, "need_products": ["savings"], "missing": "Savings balance"}, ["savings"]),
    ({"done": False, "need_other_data": True, "missing": "Transactions"}, ["other_data"]),
    ({"done": False, "need_products": ["checking"], "need_other_data": True, "missing": "Both"},
     ["checking", "other_data"]),
])
def test_incomplete_decisions_route_back_to_exact_targets(decision, expected):
    s = state()
    s.update(verify(s, planner_returning(decision)))
    assert after_verify(s) == "eval_query"
    s.update(eval_query(s, Mock()))
    assert route_to_products(s) == expected


def test_incomplete_without_targets_stops_with_caveat():
    update = verify(state(), planner_returning({"done": False, "missing": "Please name the account."}))
    assert after_verify(update) == "gen_ui" and update["verify"].missing == "Please name the account."


def test_provider_failure_stops_with_caveat_and_no_leak():
    planner = Mock()
    planner.with_structured_output.return_value.invoke.side_effect = ConnectionError("secret-token")
    update = verify(state(), planner)
    assert not update["verify"].done and "secret-token" not in update["verify"].missing
    assert update["verify"].missing == "Verification is unavailable (ConnectionError)."
    assert after_verify(update) == "gen_ui"


def test_repeated_incomplete_decisions_terminate_at_cap_without_claiming_verified():
    again = {"done": False, "need_products": ["checking"], "missing": "Still unclear"}
    planner = planner_returning(*[again] * 10)
    s, rounds = state(route=RouteDecision(products=["checking"], reasoning="Balance")), 0
    while True:
        s.update(verify(s, planner))
        rounds += 1
        if after_verify(s) == "gen_ui":
            break
    assert rounds == MAX_ITERATIONS == s["iterations"]
    assert not s["verify"].done and not s["verify"].need_products
    assert s["verify"].missing == "Still unclear (Verification limit reached.)"
