from test_retrieval import seeded, world  # noqa: F401  (seeded fake Nessie + real ProfileService)


def test_new_goal_deposit_moves_the_goal(world):  # noqa: F811
    service, client, db = world["service"], world["client"], world["db"]
    before = service.get("stu-002", refresh=True).goal
    assert before.current_saved == world["bundles"]["stu-002"].unified.goal.current_saved  # seeded data unchanged
    savings = db.nessie_id_map.find_one({"profile_id": "stu-002", "resource": "account",
                                         "local_key": {"$regex": "savings"}})["nessie_id"]
    client.create(f"/accounts/{savings}/transfers", {"transaction_date": "2026-11-09", "status": "completed",
                                                      "amount": 50, "description": "Goal contribution (in)"})
    after = service.get("stu-002", refresh=True)
    assert after.goal.current_saved == before.current_saved + 50
    assert any(t.category == "goal_contribution" and t.amount == 50 and t.date.isoformat() == "2026-11-09"
               for t in after.transactions)
