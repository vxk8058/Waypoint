from datetime import date, timedelta
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.database.mongo import get_database
from backend.services import missions
from test_agent_api import SETTINGS, world  # noqa: F401  (stu-002 profile behind a mock ProfileService)
from test_main_graph import scripted

TODAY = date(2026, 11, 9)


def pick(**choice):
    return scripted(MissionChoice=[choice])[0]


@pytest.fixture
def p(primary):
    return primary.unified


def test_summary_is_code_computed_and_skips_essentials(p):
    s = missions.summary(p)
    assert not set(s["weekly_spending_by_category"]) & missions.ESSENTIAL
    assert s["goal"]["target"] == p.goal.target_amount and s["monthly_income"] == p.wellness_inputs.monthly_income_avg


def test_ai_pick_is_checked_and_numbers_set_by_code(p):
    usual = missions._usual(p, "week", "dining", None)
    m = missions.generate(p, "week", "u1", TODAY, pick(kind="spend_cap", category="dining", amount=10_000,
                                                       why="You've got this!"))
    assert m["amount"] == int(usual * 0.9) and m["usual"] == usual  # an AI cap above usual becomes a real cutback
    assert m["why"] == "You've got this!" and m["end"] == (TODAY + timedelta(days=7)).isoformat()
    day = missions.generate(p, "day", "u1", TODAY, pick(kind="spend_cap", category="dining", amount=1, why="Save 50 today"))
    assert day["why"] == "" and day["end"] == (TODAY + timedelta(days=1)).isoformat()  # numbers only from code
    save = missions.generate(p, "week", "u1", TODAY, pick(kind="save", amount=99_999))
    w = p.wellness_inputs
    assert save["kind"] == "save" and save["amount"] == round((w.monthly_income_avg - w.monthly_spending_avg) * 12 / 365 * 7)


@pytest.mark.parametrize("choice", [
    {"kind": "spend_cap", "category": "housing", "amount": 100},     # essentials are never targets
    {"kind": "spend_cap", "merchant": "Nowhere Inc", "amount": 5},     # not something they spend on
    {"kind": "spend_cap", "amount": 5},                                # no target at all
])
def test_unusable_picks_and_model_failures_fall_back_to_code(p, choice):
    fallback = missions._fallback(p, "week")
    assert missions.generate(p, "week", "u1", TODAY, pick(**choice))["category"] == fallback["category"]
    broken = Mock()
    broken.with_structured_output.side_effect = ConnectionError("model down")
    assert missions.generate(p, "week", "u1", TODAY, broken)["amount"] == fallback["amount"]


def test_progress_for_caps_and_savings(p):
    cap = {"kind": "spend_cap", "category": "dining", "merchant": None, "label": "dining", "amount": 30, "usual": 40,
           "start": "2026-10-01", "end": "2026-10-08", "period": "week"}
    spent = sum(t.amount if t.direction == "out" else -t.amount for t in p.transactions
                if t.flow_class == "expense" and t.category == "dining" and date(2026, 10, 1) <= t.date < date(2026, 10, 8))
    assert missions.progress(cap, p, date(2026, 10, 3)).items() >= {"progress": spent, "status": "active", "days_left": 5}.items()
    save = {**cap, "kind": "save", "label": p.goal.name, "amount": 1, "start": "2026-10-01", "end": "2026-11-01"}
    assert missions.progress(save, p, date(2026, 10, 3))["status"] == "met"  # a goal deposit happened that month


def test_mission_endpoints(world, monkeypatch):  # noqa: F811
    service, _ = world
    monkeypatch.setattr(missions, "get_llm", lambda *a, **k: pick(kind="spend_cap", category="dining", amount=1,
                                                                    why="Small wins add up."))
    app = create_app(db=get_database(client=mongomock.MongoClient(), db_name="missions"), profiles=service,
                     settings=SETTINGS, agent=Mock())
    with TestClient(app) as client:
        assert client.get("/api/me/mission").status_code == 401
        token = client.post("/auth/login", json={"email": "poyo@waypoint.demo", "password": "pw-123"}).json()
        h = {"Authorization": f"Bearer {token['access_token']}"}
        assert client.get("/api/me/mission", headers=h).json() == {"week": None, "day": None}
        week = client.post("/api/me/mission?period=week", json={"amount": 999}, headers=h).json()["mission"]
        assert week["amount"] == 1 and week["why"] == "Small wins add up." and week["status"] == "active"
        assert client.post("/api/me/mission?period=week", headers=h).status_code == 409  # one per period
        day = client.post("/api/me/mission?period=day", headers=h).json()["mission"]
        assert day["period"] == "day" and day["days_left"] == 1
        both = client.get("/api/me/mission", headers=h).json()
        assert both["week"]["period"] == "week" and both["day"]["period"] == "day"
        assert client.post("/api/me/mission?period=month", headers=h).status_code == 422
