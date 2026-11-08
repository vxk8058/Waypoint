import copy
from unittest.mock import Mock

import pytest

from backend.agent.data import get_data
from backend.agent.nodes.gen_ui import build_document, gen_ui
from backend.agent.schemas import ProductResult, VerifyDecision
from backend.agent.ui.components import validate_document
from backend.agent.ui.datasets import build_datasets, build_facts
from backend.agent.ui.plan import UIPlan
from backend.agent.ui.validate import plan_problems
from backend.services.profile_service import ProfileService


@pytest.fixture
def profile(primary):
    return primary.unified.model_copy(deep=True)


def result(profile, source, errors=()):
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    data = get_data(service, profile.profile_id, source)
    if source == "transactions":
        return ProductResult(product="other_data", data={"transactions": data}, summary="Txns $1.", confidence=0.8)
    data["balance_total"] = sum(a["balance"] for a in data["accounts"])
    if "goal" in data:
        data["goal_remaining"] = max(0, data["goal"]["target_amount"] - data["goal"]["current_saved"])
    return ProductResult(product=source, data=data, errors=list(errors), summary="Summary $999.", confidence=0.9)


def october_spending(profile):
    totals = {}
    for t in profile.transactions:
        if t.flow_class == "expense" and t.date.isoformat().startswith("2026-10"):
            totals[t.category] = totals.get(t.category, 0) + (t.amount if t.direction == "out" else -t.amount)
    return {k: v for k, v in totals.items() if v > 0}


def planner(*plans):
    model = Mock()
    model.with_structured_output.return_value.invoke.side_effect = list(plans)
    return model


# 11b: datasets


def test_monthly_spending_is_exact_and_excludes_transfers_interest_and_income(profile):
    datasets = build_datasets([result(profile, "transactions")])
    october = datasets["spending_by_category.2026-10"]
    expected = october_spending(profile)
    assert dict(zip(october["keys"], october["series"][0]["values"])) == expected
    assert october["series"][0]["values"] == sorted(expected.values(), reverse=True)
    assert not {"credit_card_payment", "goal_contribution", "debt_interest", "payroll"} & set(october["keys"])
    assert all(isinstance(v, int) for v in october["series"][0]["values"])
    months = datasets["income_vs_spending"]
    assert months["keys"] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert months["series"][1]["values"][-1] == sum(expected.values())


def test_refunds_reduce_spending_and_duplicates_across_branches_count_once(profile):
    refund = profile.transactions[0].model_copy(update={
        "transaction_id": "refund-1", "date": profile.transactions[0].date.replace(month=10, day=30),
        "category": "dining", "amount": 5, "direction": "in", "flow_class": "expense"})
    profile.transactions.append(refund)
    both = [result(profile, "credit_card"), result(profile, "checking"), result(profile, "transactions")]
    october = build_datasets(both)["spending_by_category.2026-10"]
    assert dict(zip(october["keys"], october["series"][0]["values"]))["dining"] == october_spending(profile)["dining"]
    assert october_spending(profile)["dining"] == sum(
        t.amount for t in profile.transactions if t.category == "dining" and t.direction == "out"
        and t.date.isoformat().startswith("2026-10")) - 5


def test_facts_use_trusted_balances_and_goal(profile):
    facts = build_facts([result(profile, "savings"), result(profile, "loans")], {})
    savings = sum(a.balance for a in profile.accounts if a.type == "savings")
    assert facts["savings.balance"]["value"] == savings and facts["savings.balance"]["good"] == "up"
    assert facts["savings.goal_remaining"]["value"] == profile.goal.target_amount - profile.goal.current_saved
    assert facts["loans.balance"]["label"] == "Loans balance owed" and facts["loans.balance"]["good"] == "down"


# 11c / 11f: plan validation


def test_invalid_plan_choices_cannot_introduce_data(profile):
    results = [result(profile, "transactions")]
    datasets = build_datasets(results)
    facts = build_facts(results, datasets)
    plan = UIPlan(answer="You spent $500 on {made.up}.", stats=["nope"],
                  charts=[{"dataset": "invented", "title": "Top 5"}])
    problems = plan_problems(plan, facts, datasets)
    assert len(problems) == 5
    with pytest.raises(ValueError):
        UIPlan(answer="x", charts=[{"dataset": "a", "title": "t"}] * 4)
    with pytest.raises(ValueError):
        UIPlan(answer="x", stats=["a"], values=[1])


# 11d: builder


def test_builder_emits_source_values_and_valid_schema(profile):
    results = [result(profile, "transactions")]
    datasets = build_datasets(results)
    snapshot = copy.deepcopy(datasets)
    facts = build_facts(results, datasets)
    plan = UIPlan(answer="Dining cost {spending_by_category.2026-10.spent.dining}.", charts=[
        {"dataset": "spending_by_category.2026-10", "title": "Spending by category, October", "sort": "desc",
         "orientation": "horizontal", "highlight": ["Dining", "Invented"], "caption": "Dining leads."},
        {"dataset": "income_vs_spending", "title": "Income and spending by month", "sort": "desc"}])
    doc = validate_document(build_document(plan, datasets, facts, []))
    bar, _, months = doc["blocks"][1:]
    assert bar["props"]["series"] == datasets["spending_by_category.2026-10"]["series"]
    assert bar["props"]["highlight"] == ["Dining"] and bar["props"]["valueFormat"] == {"style": "currency", "decimals": 0}
    assert months["props"]["sort"] == "none"
    assert doc["blocks"][0]["props"]["text"] == f"Dining cost ${october_spending(profile)['dining']:,}."
    bar["props"]["series"][0]["values"][0] = -1
    assert datasets == snapshot


def test_balance_only_answer_has_stats_and_no_chart(profile):
    savings = result(profile, "savings")
    update = gen_ui({"query": "What's my savings balance?", "results": [savings],
                     "verify": VerifyDecision(done=True)},
                    planner({"answer": "Your savings balance is {savings.balance}.", "stats": ["savings.balance"]}))
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "stats"]
    assert blocks[1]["props"]["items"][0]["value"] == savings.data["balance_total"]


# 11f: end-to-end grounding, regeneration, fallback


def test_raw_number_triggers_one_regeneration(profile):
    model = planner({"answer": "You spent $1,234."}, {"answer": "You spent {income_vs_spending.spending.total}."})
    update = gen_ui({"query": "Spending?", "results": [result(profile, "transactions")]}, model)
    assert model.with_structured_output.return_value.invoke.call_count == 2
    second = model.with_structured_output.return_value.invoke.call_args.args[0]
    assert "previous plan was rejected" in second and "$1,234" in second
    assert "$1,234" not in update["final_ui"]["blocks"][0]["props"]["text"]


def test_repeated_ungrounded_text_falls_back_with_caveats(profile):
    checking = result(profile, "checking", errors=["Checking data is a stale snapshot"])
    bad = {"answer": "Your balance is $1,000,000.", "charts": [{"dataset": "income_vs_spending", "title": "x"}]}
    model = planner(bad, bad, bad)
    update = gen_ui({"query": "Balance?", "results": [checking],
                     "verify": VerifyDecision(done=False, missing="Recent deposits are missing")}, model)
    assert model.with_structured_output.return_value.invoke.call_count == 2
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "stats", "callout"]
    assert "1,000,000" not in str(blocks)
    assert blocks[1]["props"]["items"][0]["value"] == checking.data["balance_total"]
    assert blocks[2]["props"]["text"] == "Checking data is a stale snapshot Recent deposits are missing"


def test_planner_failure_and_no_results_use_code_only_fallback(profile):
    model = Mock()
    model.with_structured_output.return_value.invoke.side_effect = ConnectionError("secret-token")
    update = gen_ui({"query": "Balance?", "results": [result(profile, "checking")]}, model)
    assert "secret-token" not in str(update) and update["final_ui"]["blocks"][1]["type"] == "stats"
    unused = Mock()
    update = gen_ui({"query": "Help", "results": [],
                     "verify": VerifyDecision(done=False, missing="Please name an account.")}, unused)
    unused.with_structured_output.assert_not_called()
    assert update["final_ui"]["blocks"][-1]["props"]["text"] == "Please name an account."


def test_numeric_verify_caveat_is_replaced():
    update = gen_ui({"query": "x", "results": [], "verify": VerifyDecision(done=False, missing="Owes $5,000")})
    assert update["final_ui"]["blocks"][-1]["props"]["text"] == "Some requested information could not be verified."
