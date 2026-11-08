"""Step 13: the guide's seven scenarios through the authenticated API, with scripted (not live) models."""
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.agent.graph import build_agent_graph
from backend.api.app import create_app
from backend.auth import tokens
from backend.config import Settings
from backend.database.mongo import get_database
from backend.services.profile_service import ProfileService
from test_main_graph import scripted

SETTINGS = Settings(nessie_api_key=None, nessie_base_url="https://fake", mongodb_uri=None, mongodb_db="agent_api",
                    session_secret="test-secret", demo_password="pw-123")


@pytest.fixture
def world(bundles):
    profiles = {}
    for b in bundles:
        profile = b.unified.model_copy(deep=True)
        profile.data_mode, profile.metadata = "nessie", {"stale": False, "warnings": []}
        profiles[profile.profile_id] = profile
    service = Mock(spec=ProfileService)
    service.get.side_effect = lambda profile_id, refresh=False: profiles[profile_id]
    return service, profiles["stu-002"]


def ask(service, question, worker_sources=("transactions",), headers=None, **planner_outputs):
    planner, calls = scripted(**planner_outputs)
    worker, _ = scripted(SourceDecision=[{"sources": list(worker_sources)}],
                         ProductEvaluation=[{"summary": "Records reviewed.", "confidence": 0.9}])
    app = create_app(db=get_database(client=mongomock.MongoClient(), db_name="agent_api"), profiles=service,
                     settings=SETTINGS, agent=build_agent_graph(service, planner, worker))
    with TestClient(app) as client:
        if headers is None:
            token = client.post("/auth/login", json={"email": "poyo@waypoint.demo", "password": "pw-123"}).json()
            headers = {"Authorization": f"Bearer {token['access_token']}"}
        return client.post("/api/me/agent", json={"question": question}, headers=headers), calls


def kinds(response):
    return [b["type"] for b in response.json()["blocks"]]


def route(*products):
    return [{"products": list(products), "reasoning": "Needed"}]


def test_1_checking_balance(world):
    service, profile = world
    r, calls = ask(service, "What's my checking balance?", RouteDecision=route("checking"),
                   VerifyDecision=[{"done": True}],
                   UIPlan=[{"answer": "Your checking balance is {checking.balance}.", "stats": ["checking.balance"]}])
    balance = sum(a.balance for a in profile.accounts if a.type == "checking")
    assert r.status_code == 200 and kinds(r) == ["paragraph", "stats"]
    assert r.json()["blocks"][1]["props"]["items"][0]["value"] == balance
    assert len(calls["VerifyDecision"]) == 1


def test_2_savings_vs_loan_payoff_runs_in_parallel_and_flags_missing_payoff(world):
    service, profile = world
    r, calls = ask(service, "Compare my savings to my loan payoff", RouteDecision=route("savings", "loans"),
                   VerifyDecision=[{"done": False, "missing": "No loan payoff quote is available."}],
                   UIPlan=[{"answer": "Your savings balance is {savings.balance}.", "stats": ["savings.balance"]}])
    assert len(calls["VerifyDecision"]) == 1  # both branches joined before one Verify
    callout = r.json()["blocks"][-1]["props"]["text"]
    assert "No loan account is available" in callout and "No loan payoff quote is available." in callout
    assert r.json()["blocks"][1]["props"]["items"][0]["value"] == sum(
        a.balance for a in profile.accounts if a.type == "savings")


def test_3_lower_balance_fetches_transactions_after_verify(world):
    service, _ = world
    r, calls = ask(service, "Why is my balance lower than usual?", RouteDecision=route("checking"),
                   VerifyDecision=[{"done": False, "need_other_data": True, "missing": "Recent transactions"},
                                   {"done": True}],
                   UIPlan=[{"answer": "Spending outpaced income in one month.",
                            "charts": [{"dataset": "income_vs_spending", "title": "Income and spending by month"}]}])
    assert len(calls["VerifyDecision"]) == 2 and kinds(r) == ["paragraph", "bar_chart"]


def test_4_api_failure_is_a_caveat_not_a_crash(world):
    service, _ = world
    service.get.side_effect = ConnectionError("internal-host:27017")
    r, _ = ask(service, "What's my checking balance?", RouteDecision=route("checking"),
               VerifyDecision=[{"done": False, "missing": "Checking data is unavailable."}],
               UIPlan=[{"answer": "I couldn't reach your checking records."}])
    assert r.status_code == 200 and kinds(r)[-1] == "callout"
    assert "Checking retrieval failed (ConnectionError)" in r.text and "internal-host" not in r.text


def test_5_vague_query_asks_for_clarification_and_repeated_gaps_stop_at_three(world):
    service, _ = world
    r, calls = ask(service, "Help me with my money", RouteDecision=[{"products": [], "reasoning": "Which account?"}],
                   VerifyDecision=[{"done": True}], UIPlan=[{"answer": "unused"}])
    assert "VerifyDecision" not in calls and r.json()["blocks"][-1]["props"]["text"] == "Which account?"
    r, calls = ask(service, "Help me with my money", RouteDecision=route("checking"),
                   VerifyDecision=[{"done": False, "need_products": ["checking"], "missing": "Unclear goal"}],
                   UIPlan=[{"answer": "Here is your checking account."}])
    assert len(calls["VerifyDecision"]) == 3 and "Verification limit reached" in r.text


def test_6_october_spending_chart_uses_exact_totals(world):
    service, profile = world
    r, _ = ask(service, "Where did my money go in October?", RouteDecision=route("checking", "credit_card"),
               VerifyDecision=[{"done": False, "need_other_data": True, "missing": "All October transactions"},
                               {"done": True}],
               UIPlan=[{"answer": "You spent {spending_by_category.2026-10.spent.total} in October.",
                        "charts": [{"dataset": "spending_by_category.2026-10", "title": "Spending by category, October",
                                    "orientation": "horizontal", "sort": "desc"}]}])
    expected = {}
    for t in profile.transactions:
        if t.flow_class == "expense" and t.date.isoformat().startswith("2026-10"):
            expected[t.category] = expected.get(t.category, 0) + (t.amount if t.direction == "out" else -t.amount)
    chart = next(b for b in r.json()["blocks"] if b["type"] == "bar_chart")["props"]
    assert sorted(chart["series"][0]["values"], reverse=True) == sorted(expected.values(), reverse=True)
    assert r.json()["blocks"][0]["props"]["text"] == f"You spent ${sum(expected.values()):,} in October."


def test_7_savings_balance_is_text_only(world):
    service, _ = world
    r, _ = ask(service, "What's my savings balance?", RouteDecision=route("savings"), VerifyDecision=[{"done": True}],
               UIPlan=[{"answer": "Your savings balance is {savings.balance}.", "stats": ["savings.balance"]}])
    assert "bar_chart" not in kinds(r)


def test_agent_only_reads_the_signed_in_users_profile(world):
    service, _ = world
    plan = dict(RouteDecision=route("checking"), VerifyDecision=[{"done": True}], UIPlan=[{"answer": "Done."}])
    r, _ = ask(service, "What's my checking balance?", **plan)
    assert r.status_code == 200 and {c.args[0] for c in service.get.call_args_list} == {"stu-002"}
    service.get.reset_mock()
    assert ask(service, "Balance?", headers={}, **plan)[0].status_code == 401
    forged, _ = tokens.issue("other-secret", {"sub": "user-poyo", "profile_id": "stu-001"})
    assert ask(service, "Balance?", headers={"Authorization": f"Bearer {forged}"}, **plan)[0].status_code == 401
    service.get.assert_not_called()


def test_request_cannot_choose_a_profile_and_needs_a_real_question(world):
    service, _ = world
    planner, _ = scripted(RouteDecision=route("checking"))
    app = create_app(db=get_database(client=mongomock.MongoClient(), db_name="agent_api"), profiles=service,
                     settings=SETTINGS, agent=build_agent_graph(service, planner, Mock()))
    with TestClient(app) as client:
        token = client.post("/auth/login", json={"email": "poyo@waypoint.demo", "password": "pw-123"}).json()
        h = {"Authorization": f"Bearer {token['access_token']}"}
        assert client.post("/api/me/agent", json={"question": "Hi", "profile_id": "stu-001"}, headers=h).status_code == 422
        assert client.post("/api/me/agent", json={"question": "   "}, headers=h).status_code == 422
        assert client.post("/api/me/agent", json={"question": ""}, headers=h).status_code == 422
    service.get.assert_not_called()
