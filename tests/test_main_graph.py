import json
from unittest.mock import Mock

import pytest

from backend.agent.graph import build_agent_graph, run_agent
from backend.agent.schemas import ProductEvaluation, RouteDecision, VerifyDecision
from backend.agent.state import initial_state
from backend.agent.subgraphs.other_data import SourceDecision
from backend.agent.ui.plan import UIPlan
from backend.auth.users import PublicUser
from backend.services.profile_service import ProfileService

USER = PublicUser(user_id="user-1", profile_id="stu-001", email="demo@example.test",
                  display_name="Demo", first_name="Demo", last_name="User")


def scripted(**outputs):
    """A model whose structured output for each schema comes from a list (last item repeats)."""
    model, calls = Mock(), {}

    def runner(schema):
        queue = outputs[schema.__name__]
        calls.setdefault(schema.__name__, [])

        def invoke(prompt):
            calls[schema.__name__].append(prompt)
            return queue.pop(0) if len(queue) > 1 else queue[0]
        return Mock(invoke=invoke)
    model.with_structured_output.side_effect = runner
    return model, calls


@pytest.fixture
def service(primary):
    profile = primary.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    svc = Mock(spec=ProfileService)
    svc.get.return_value = profile
    return svc, profile


def worker():
    return scripted(SourceDecision=[{"sources": ["transactions"]}],
                    ProductEvaluation=[{"summary": "Records reviewed.", "confidence": 0.9}])[0]


def run(svc, planner, query="What's my checking balance?"):
    return build_agent_graph(svc, planner, worker()).invoke(initial_state(query, USER))


def test_checking_balance_path(service):
    svc, profile = service
    planner, calls = scripted(
        RouteDecision=[{"products": ["checking"], "reasoning": "Balance"}],
        VerifyDecision=[{"done": True}],
        UIPlan=[{"answer": "Your checking balance is {checking.balance}.", "stats": ["checking.balance"]}])
    out = run(svc, planner)
    balance = sum(a.balance for a in profile.accounts if a.type == "checking")
    assert [r.product for r in out["results"]] == ["checking"] and out["iterations"] == 1
    assert out["final_ui"]["blocks"][0]["props"]["text"] == f"Your checking balance is ${balance:,}."
    assert out["final_ui"]["blocks"][1]["props"]["items"][0]["value"] == balance
    assert len(calls["VerifyDecision"]) == 1 and "stu-001" not in calls["RouteDecision"][0]


def test_parallel_branches_join_before_single_verify(service):
    svc, _ = service
    planner, calls = scripted(
        RouteDecision=[{"products": ["savings", "loans"], "reasoning": "Compare"}],
        VerifyDecision=[{"done": True}],
        UIPlan=[{"answer": "Savings {savings.balance}; loans owed {loans.balance}.",
                 "stats": ["savings.balance", "loans.balance"]}])
    out = run(svc, planner, "Compare my savings to my loan payoff")
    assert {r.product for r in out["results"]} == {"savings", "loans"}
    assert len(calls["VerifyDecision"]) == 1
    products = [r["product"] for r in json.loads(calls["VerifyDecision"][0].split("\n")[-1])["results"]]
    assert sorted(products) == ["loans", "savings"]


def test_verify_requests_other_data_then_finishes(service):
    svc, _ = service
    planner, calls = scripted(
        RouteDecision=[{"products": ["checking"], "reasoning": "Balance"}],
        VerifyDecision=[{"done": False, "need_other_data": True, "missing": "Recent transactions"}, {"done": True}],
        UIPlan=[{"answer": "Spending rose; see {income_vs_spending.spending.total} over the period.",
                 "charts": [{"dataset": "income_vs_spending", "title": "Income and spending by month"}]}])
    out = run(svc, planner, "Why is my balance lower than usual?")
    assert {r.product for r in out["results"]} == {"checking", "other_data"} and out["iterations"] == 2
    assert len(calls["RouteDecision"]) == 1  # the retry follows Verify's targets without rerouting
    svc.get.assert_called_with("stu-001", refresh=True)
    assert [b["type"] for b in out["final_ui"]["blocks"]] == ["paragraph", "bar_chart"]


def test_retry_replaces_stale_results_and_cap_terminates(service):
    svc, profile = service
    refreshed = profile.model_copy(deep=True)
    next(a for a in refreshed.accounts if a.type == "checking").balance += 100
    svc.get.side_effect = [profile, refreshed, refreshed]
    planner, calls = scripted(
        RouteDecision=[{"products": ["checking"], "reasoning": "Balance"}],
        VerifyDecision=[{"done": False, "need_products": ["checking"], "missing": "Still unclear"}],
        UIPlan=[{"answer": "Your checking balance is {checking.balance}."}])
    out = run(svc, planner)
    assert out["iterations"] == 3 and len(calls["VerifyDecision"]) == 3 and svc.get.call_count == 3
    assert len(out["results"]) == 1
    new_total = sum(a.balance for a in refreshed.accounts if a.type == "checking")
    assert out["results"][0].data["balance_total"] == new_total
    assert f"Checking balance: ${new_total:,} (dollars)" in calls["VerifyDecision"][1]
    assert not out["verify"].done and out["verify"].missing.endswith("(Verification limit reached.)")
    assert "Verification limit reached" in out["final_ui"]["blocks"][-1]["props"]["text"]


def test_no_match_skips_fetch_and_verify(service):
    svc, _ = service
    planner, calls = scripted(RouteDecision=[{"products": [], "reasoning": "Please name an account."}],
                              VerifyDecision=[{"done": True}], UIPlan=[{"answer": "unused"}])
    out = run(svc, planner, "Help me with my money")
    svc.get.assert_not_called()
    assert "VerifyDecision" not in calls and "UIPlan" not in calls
    assert out["final_ui"]["blocks"][-1]["props"]["text"] == "Please name an account."


def test_api_failure_becomes_caveat_without_crash(service):
    svc, _ = service
    svc.get.side_effect = ConnectionError("secret")
    planner, _ = scripted(
        RouteDecision=[{"products": ["checking"], "reasoning": "Balance"}],
        VerifyDecision=[{"done": False, "missing": "Checking data could not be retrieved."}],
        UIPlan=[{"answer": "unused"}])
    out = run(svc, planner)
    assert "Checking retrieval failed (ConnectionError)" in out["final_ui"]["blocks"][-1]["props"]["text"]
    assert "secret" not in json.dumps(out["final_ui"])


def test_run_agent_logs_path_retries_and_termination_without_data(service, caplog):
    svc, profile = service
    svc.get.side_effect = [ConnectionError("secret-host")] + [profile] * 10
    planner, _ = scripted(
        RouteDecision=[{"products": ["checking"], "reasoning": "Private reasoning"}],
        VerifyDecision=[{"done": False, "need_products": ["checking"], "need_other_data": True,
                         "missing": "Private missing detail"}],
        UIPlan=[{"answer": "Your checking balance is {checking.balance}."}])
    worker_model = scripted(SourceDecision=[{"sources": ["transactions"]}],
                            ProductEvaluation=[{"summary": "Private summary", "confidence": 0.9}])[0]
    graph = build_agent_graph(svc, planner, worker_model)
    caplog.set_level("INFO", logger="waypoint.agent")
    out = run_agent(graph, initial_state("My private question", USER))
    lines = [r.getMessage() for r in caplog.records if r.name == "waypoint.agent"]
    nodes = [line.split()[1] for line in lines]
    assert nodes[0] == "node=eval_query" and nodes[-1] == "node=gen_ui"
    assert nodes.count("node=verify") == 3 and nodes.count("node=eval_query") == 3
    assert "agent node=checking confidence=0.0 errors=1" in lines  # the failed first fetch
    assert "round=3 done=False need_products=[] need_other_data=False" in lines[-2]
    assert out["final_ui"]["blocks"][0]["props"]["text"].startswith("Your checking balance is $")
    balance = str(sum(a.balance for a in profile.accounts if a.type == "checking"))
    logged = "\n".join(lines)
    for private in ("My private question", "stu-001", "user-1", "Private", "secret-host", balance):
        assert private not in logged


# Calculate plan, step 4: Verify → Calculate → Verify

CAR = "If I add $100 a day for the next month, how much more quickly can I get my car?"
DAYS = {"name": "days_needed", "label": "Days to reach goal", "unit": "days",
        "formula": "ceil({savings.goal_remaining} / 100)"}


def savings_route(*verify):
    return scripted(RouteDecision=[{"products": ["savings"], "reasoning": "Goal"}], VerifyDecision=list(verify),
                    UIPlan=[{"answer": "Here is your goal progress."}])


def test_verify_requests_calculation_then_finishes(service, caplog):
    svc, profile = service
    planner, calls = savings_route({"done": False, "missing": "Days at $100 a day", "calculations": [DAYS]},
                                   {"done": True})
    caplog.set_level("INFO", logger="waypoint.agent")
    out = run_agent(build_agent_graph(svc, planner, worker()), initial_state(CAR, USER))
    remaining = profile.goal.target_amount - profile.goal.current_saved
    assert out["calculations"] == [{**DAYS, "value": -(-remaining // 100)}]
    assert out["iterations"] == 2 and out["verify"].done and svc.get.call_count == 1  # no re-fetch
    assert f'"value": {-(-remaining // 100)}' in calls["VerifyDecision"][1]
    nodes = [r.getMessage().split()[1] for r in caplog.records if r.name == "waypoint.agent"]
    assert nodes == ["node=eval_query", "node=savings", "node=verify", "node=calculate", "node=verify", "node=gen_ui"]
    assert "agent node=calculate count=1 errors=0" in [r.getMessage() for r in caplog.records]
    assert "ceil" not in caplog.text and "goal_remaining" not in caplog.text


def test_failed_formula_can_be_corrected_and_chained(service):
    svc, profile = service
    bad = {**DAYS, "formula": "{savings.goal_remaining} / 250"}  # 250 isn't in the question
    weeks = {"name": "weeks_needed", "label": "Weeks to reach goal", "unit": "count", "formula": "ceil(days_needed / 7)"}
    planner, calls = savings_route({"done": False, "missing": "Days", "calculations": [bad]},
                                   {"done": False, "missing": "Fix it", "calculations": [DAYS, weeks]},
                                   {"done": True})
    out = build_agent_graph(svc, planner, worker()).invoke(initial_state(CAR, USER))
    assert '"error": "Number 250 is not in the question or the allowed constants"' in calls["VerifyDecision"][1]
    days = -(-(profile.goal.target_amount - profile.goal.current_saved) // 100)
    assert [(c["name"], c.get("value")) for c in out["calculations"]] == [("days_needed", days),
                                                                            ("weeks_needed", -(-days // 7))]
    assert out["verify"].done and out["iterations"] == 3


def test_repeated_calculation_requests_stop_at_round_limit(service):
    svc, _ = service
    planner, calls = savings_route({"done": False, "missing": "More maths", "calculations": [DAYS]})
    out = build_agent_graph(svc, planner, worker()).invoke(initial_state(CAR, USER))
    assert len(calls["VerifyDecision"]) == 3 and out["iterations"] == 3
    assert not out["verify"].done and out["verify"].missing == "More maths (Verification limit reached.)"
    assert "Verification limit reached" in out["final_ui"]["blocks"][-1]["props"]["text"]


def test_calculate_without_record_date_reports_errors():
    from backend.agent.nodes.calculate import calculate
    state = {"query": CAR, "results": [], "calculations": [],
             "verify": VerifyDecision(done=False, missing="x", calculations=[DAYS])}
    assert calculate(state)["calculations"] == [{**DAYS, "error": "No record date is available for calculations"}]


def test_calculated_answer_end_to_end(service):
    svc, profile = service
    planner, _ = scripted(
        RouteDecision=[{"products": ["savings"], "reasoning": "Goal"}],
        VerifyDecision=[{"done": False, "missing": "Days at $100 a day", "calculations": [DAYS]}, {"done": True}],
        UIPlan=[{"answer": "Adding that, you'd reach your goal in {calc.days_needed}.",
                 "stats": ["calc.days_needed", "savings.goal_remaining"]}])
    out = build_agent_graph(svc, planner, worker()).invoke(initial_state(CAR, USER))
    days = -(-(profile.goal.target_amount - profile.goal.current_saved) // 100)
    blocks = out["final_ui"]["blocks"]
    assert blocks[0]["props"]["text"] == f"Adding that, you'd reach your goal in {days} days."
    assert blocks[2]["props"]["text"].endswith(f"÷ 100) = {days} days.")
