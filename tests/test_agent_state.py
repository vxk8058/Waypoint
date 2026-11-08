from typing import get_type_hints

import pytest

from backend.agent.schemas import ProductResult, RouteDecision, VerifyDecision
from backend.agent.state import AgentState, initial_state, merge_results
from backend.auth.users import PublicUser


def result(product, balance=100, errors=None):
    return ProductResult(product=product, summary="Retrieved balance" if not errors else "Unavailable",
                         confidence=1 if not errors else 0,
                         data={"balance": balance} if not errors else {}, errors=errors or [])


def user(profile_id):
    return PublicUser(user_id=f"user-{profile_id}", profile_id=profile_id, email="demo@example.test",
                      display_name="Demo", first_name="Demo", last_name="User")


def test_independent_branch_results_are_preserved_in_either_order():
    savings, loans = result("savings"), result("loans")
    forward = merge_results(merge_results([], [savings]), [loans])
    reverse = merge_results(merge_results([], [loans]), [savings])
    assert {r.product: r for r in forward} == {r.product: r for r in reverse} == {
        "savings": savings, "loans": loans,
    }


@pytest.mark.parametrize("errors", [[], ["API unavailable"]])
def test_refetch_replaces_stale_result_even_on_failure(errors):
    old, savings = result("checking", 100), result("savings", 200)
    new = result("checking", 300, errors)
    current, updates = [old, savings], [new]
    merged = merge_results(current, updates)
    assert merged == [new, savings]
    assert current == [old, savings] and updates == [new]
    if errors:
        assert merged[0].data == {} and merged[0].errors == errors


def test_empty_updates_preserve_results_without_reusing_the_list():
    current = [result("checking")]
    merged = merge_results(current, [])
    assert merged == current and merged is not current
    assert merge_results([], []) == []


def test_result_reducer_is_attached_to_graph_state():
    annotation = get_type_hints(AgentState, include_extras=True)["results"]
    assert annotation.__metadata__ == (merge_results,)


def test_requests_start_fresh_for_same_and_different_users():
    first = initial_state(" Balance? ", user("stu-001"))
    first["results"].append(result("checking"))
    first.update(route=RouteDecision(products=["checking"], reasoning="Balance"),
                 verify=VerifyDecision(done=True), iterations=3, final_ui={"components": []})
    for profile_id in ("stu-001", "stu-002"):
        fresh = initial_state("Savings?", user(profile_id))
        assert fresh == {"query": "Savings?", "user_id": f"user-{profile_id}",
                         "profile_id": profile_id, "results": [], "iterations": 0}
        assert fresh["results"] is not first["results"]
    assert first["query"] == "Balance?"


@pytest.mark.parametrize("query", ["", " \n\t "])
def test_blank_query_is_rejected(query):
    with pytest.raises(ValueError, match="question"):
        initial_state(query, user("stu-001"))
