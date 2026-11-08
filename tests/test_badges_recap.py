from datetime import date
from unittest.mock import Mock

import mongomock
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.database.mongo import get_database
from backend.services import badges, missions, recap
from test_agent_api import SETTINGS, world  # noqa: F401
from test_main_graph import scripted

TODAY = date(2026, 11, 9)


def met_mission(p, start, end):  # a dining cap so high it is always met
    return {"kind": "spend_cap", "category": "dining", "merchant": None, "label": "dining", "amount": 99_999,
            "usual": 1, "start": start, "end": end, "period": "week"}


def test_badges_come_from_verified_records_and_are_kept(primary):
    p = primary.unified.model_copy(deep=True)  # goal $1,500 of $3,000, a deposit every month May–Oct
    assert badges.earned_now(p, [], TODAY) == {"goal_25", "goal_50", "saved_100", "saved_500", "saved_1000",
                                               "streak_3", "streak_6"}
    three = [met_mission(p, f"2026-10-0{d}", f"2026-10-0{d + 1}") for d in (1, 3, 5)]
    assert {"mission_1", "mission_3"} <= badges.earned_now(p, three, TODAY)
    db = get_database(client=mongomock.MongoClient(), db_name="badges")
    first = {b["id"] for b in badges.badges(db, "u1", p, TODAY) if b["earned"]}
    p.goal.current_saved = 50  # a later withdrawal
    kept = {b["id"]: b for b in badges.badges(db, "u1", p, TODAY)}
    assert {i for i, b in kept.items() if b["earned"]} == first and kept["goal_50"]["earned_on"] == TODAY.isoformat()
    assert kept["saved_2500"] == {"id": "saved_2500", "label": "$2,500 saved", "hint": "Save $2,500 toward your goal",
                                  "earned": False, "earned_on": None}


def test_recap_numbers_come_from_transactions(primary):
    p = primary.unified
    assert recap.window(p, "last7", TODAY) == (date(2026, 10, 25), date(2026, 10, 31))
    assert recap.window(p, "calendar", TODAY) == (date(2026, 10, 19), date(2026, 10, 25))  # last full Mon–Sun
    doc = recap.recap(p, [], [], "last7", TODAY)
    spent = sum(t.amount if t.direction == "out" else -t.amount for t in p.transactions
                if t.flow_class == "expense" and date(2026, 10, 25) <= t.date <= date(2026, 10, 31))
    stats = next(b for b in doc["blocks"] if b["type"] == "stats")["props"]["items"]
    assert doc["blocks"][0]["props"]["text"] == "Your week: Oct 25 – Oct 31" and stats[0]["value"] == spent


def test_badge_recap_and_hinted_mission_endpoints(world, monkeypatch):  # noqa: F811
    service, _ = world
    model, calls = scripted(MissionChoice=[{"kind": "spend_cap", "category": "dining", "amount": 1}])
    monkeypatch.setattr(missions, "get_llm", lambda *a, **k: model)
    app = create_app(db=get_database(client=mongomock.MongoClient(), db_name="br"), profiles=service,
                     settings=SETTINGS, agent=Mock())
    with TestClient(app) as client:
        assert client.get("/api/me/badges").status_code == 401 and client.get("/api/me/recap").status_code == 401
        token = client.post("/auth/login", json={"email": "poyo@waypoint.demo", "password": "pw-123"}).json()
        h = {"Authorization": f"Bearer {token['access_token']}"}
        assert len(client.get("/api/me/badges", headers=h).json()) == len(badges.BADGES)
        assert client.get("/api/me/recap?mode=calendar", headers=h).json()["blocks"][0]["type"] == "heading"
        assert client.get("/api/me/recap?mode=year", headers=h).status_code == 422
        r = client.post("/api/me/mission?period=week", json={"hint": "What if I cut dining out in half?"}, headers=h)
        assert r.status_code == 200 and "What if I cut dining out in half?" in calls["MissionChoice"][0]
