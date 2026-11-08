from unittest.mock import Mock

import pytest

from backend.agent.nodes.eval_query import eval_query, route_to_products
from backend.agent.nodes.verify import MAX_ITERATIONS, after_verify, verify
from backend.agent.schemas import Calculation, ProductResult, RouteDecision, VerifyDecision

TXN = {"transaction_id": "t1", "date": "2026-10-03", "account_type": "checking", "direction": "out", "amount": 40,
       "flow_class": "expense", "category": "dining", "description": "PRIVATE-MERCHANT"}
RESULT = ProductResult(product="checking", data={
    "accounts": [{"balance": 1234}], "balance_total": 1234, "transactions": [TXN], "as_of_date": "2026-10-31",
    "metadata": {"stale": True}}, errors=["Checking data is a stale snapshot"], summary="Balance is $1,234.",
    confidence=0)
CALC = {"name": "days_needed", "label": "Days to goal", "unit": "days", "formula": "ceil({checking.balance} / 100)"}


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
    assert "Checking balance: $1,234 (dollars)" in prompt and "stale snapshot" in prompt
    assert '"as_of_date": "2026-10-31"' in prompt and "Spent, Dining: $40 (dollars)" in prompt
    assert "private-profile" not in prompt and "PRIVATE-MERCHANT" not in prompt  # facts, not raw records
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


# Calculate plan, step 3: Verify can request calculations


def test_calculation_request_routes_to_calculate_and_keeps_round_count():
    update = verify(state(), planner_returning({"done": False, "missing": "Working out days", "calculations": [CALC]}))
    assert after_verify(update) == "calculate" and update["iterations"] == 1
    assert update["verify"].calculations[0].formula == CALC["formula"]


def test_previous_calculation_results_reach_the_prompt():
    planner = planner_returning({"done": True})
    verify(state(calculations=[{**CALC, "value": 13}, {**CALC, "name": "bad", "error": "Division by zero"}]), planner)
    prompt = planner.with_structured_output.return_value.invoke.call_args.args[0]
    assert '"value": 13' in prompt and '"error": "Division by zero"' in prompt


def test_round_limit_drops_pending_calculations():
    planner = planner_returning({"done": False, "missing": "Still calculating", "calculations": [CALC]})
    update = verify(state(iterations=MAX_ITERATIONS - 1), planner)
    assert update["verify"].calculations == [] and after_verify(update) == "gen_ui"
    assert update["verify"].missing == "Still calculating (Verification limit reached.)"


@pytest.mark.parametrize("decision", [
    {"done": True, "calculations": [CALC]},
    {"done": False, "missing": "x", "need_products": ["savings"], "calculations": [CALC]},
    {"done": False, "missing": "x", "need_other_data": True, "calculations": [CALC]},
    {"done": False, "missing": "x", "calculations": [CALC, CALC]},
    {"done": False, "missing": "x", "calculations": [{**CALC, "name": f"c{i}"} for i in range(6)]},
    {"done": False, "missing": "x", "calculations": [{**CALC, "name": "ceil"}]},
    {"done": False, "missing": "x", "calculations": [{**CALC, "name": "Days Needed"}]},
    {"done": False, "missing": "x", "calculations": [{**CALC, "unit": "dollars_per_day"}]},
    {"done": False, "missing": "x", "calculations": [{**CALC, "extra": 1}]},
    {"done": False, "calculations": [CALC]},
])
def test_invalid_calculation_decisions_are_rejected(decision):
    with pytest.raises(ValueError):
        VerifyDecision.model_validate(decision)


def test_valid_calculation_model():
    assert Calculation.model_validate(CALC).unit == "days"
