"""Step 15: the agent over the real ProfileService/Nessie retrieval path (fake Nessie server, scripted models)."""
import json

from backend.agent.graph import build_agent_graph
from backend.agent.state import initial_state
from backend.auth.users import PublicUser
from test_main_graph import scripted
from test_retrieval import seeded, world  # noqa: F401  (shared seeded fake Nessie fixtures)

ALL = ["checking", "savings", "credit_card", "loans"]


def user(profile_id):
    return PublicUser(user_id=f"user-{profile_id}", profile_id=profile_id, email="demo@example.test",
                      display_name="Demo", first_name="Demo", last_name="User")


def run(world, profile_id, verify, products=ALL):
    planner, calls = scripted(RouteDecision=[{"products": products, "reasoning": "Needed"}], VerifyDecision=verify,
                              UIPlan=[{"answer": "Here is what your records show."}])
    worker, _ = scripted(SourceDecision=[{"sources": ["transactions"]}],
                         ProductEvaluation=[{"summary": "Records reviewed.", "confidence": 0.9}])
    graph = build_agent_graph(world["service"], planner, worker)
    start = len(world["fake"].requests)
    out = graph.invoke(initial_state("Review my accounts", user(profile_id)))
    return out, world["fake"].requests[start:], calls


def test_every_branch_reads_nessie_backed_data_without_writes(world):
    world["clock"][0] += 61  # expire any cache so the run itself reads Nessie
    out, requests, _ = run(world, "stu-001", [
        {"done": False, "need_other_data": True, "missing": "Transactions"}, {"done": True}])
    assert requests and {method for method, _ in requests} == {"GET"}
    expected = world["service"].get("stu-001")
    by_product = {r.product: r for r in out["results"]}
    assert set(by_product) == {*ALL, "other_data"}
    for product, result in by_product.items():
        data = result.data["transactions"] if product == "other_data" else result.data
        assert data["profile_id"] == "stu-001" and data["data_mode"] == "nessie" and result.errors == []
    for product, types in {"checking": {"checking"}, "savings": {"savings"}, "credit_card": {"credit_card"},
                           "loans": {"student_loan", "auto_loan"}}.items():
        assert by_product[product].data["balance_total"] == sum(a.balance for a in expected.accounts if a.type in types)
    assert len(by_product["other_data"].data["transactions"]["transactions"]) == len(expected.transactions)


def test_nessie_outage_serves_stale_snapshot_with_caveat_and_no_internals(world):
    world["service"].get("stu-001")  # saves a snapshot
    world["clock"][0] += 61
    for _ in range(100):
        world["fake"].fail("GET", r"^/", 503)
    out, requests, _ = run(world, "stu-001", [{"done": True}], ["checking"])
    assert {method for method, _ in requests} == {"GET"}
    result = out["results"][0]
    assert result.data["metadata"]["stale"] is True and result.confidence == 0
    ui = json.dumps(out["final_ui"])
    assert "Nessie unavailable (NessieError); serving last snapshot" in ui and "stale snapshot" in ui
    assert "/customers" not in ui and "injected failure" not in ui


def test_unseeded_profile_is_labeled_pre_seed(world):
    world["db"].nessie_id_map.delete_many({"profile_id": "stu-003"})
    out, requests, _ = run(world, "stu-003", [{"done": True}], ["savings"])
    assert requests == []
    assert "synthetic pre-seed data" in json.dumps(out["final_ui"])
