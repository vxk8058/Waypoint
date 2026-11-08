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


def test_balance_answer_gets_goal_progress_chart(profile):
    savings = result(profile, "savings")
    update = gen_ui({"query": "What's my savings balance?", "results": [savings],
                     "verify": VerifyDecision(done=True)},
                    planner({"answer": "Your savings balance is {savings.balance}.", "stats": ["savings.balance"]}))
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "stats", "bar_chart"]
    assert blocks[1]["props"]["items"][0]["value"] == savings.data["balance_total"]
    goal = profile.goal
    assert blocks[2]["props"]["title"] == f"{goal.name} progress"
    assert blocks[2]["props"]["categories"] == [f"Saved toward {goal.name}", f"{goal.name} target"]
    assert blocks[2]["props"]["series"] == [{"name": "Amount", "values": [goal.current_saved, goal.target_amount]}]


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
    assert [b["type"] for b in blocks] == ["paragraph", "stats", "bar_chart", "callout"]
    assert "1,000,000" not in str(blocks)
    assert blocks[1]["props"]["items"][0]["value"] == checking.data["balance_total"]
    assert blocks[2]["props"]["title"].startswith("Spending by category, October 2026")
    assert blocks[3]["props"]["text"] == "Checking data is a stale snapshot Recent deposits are missing"


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


# Calculate plan, step 1: fact units and everyday-maths facts


@pytest.mark.parametrize("unit,value,text", [
    ("dollars", 1800, "$1,800"), ("dollars", -120, "-$120"), ("dollars", 1799.6, "$1,800"),
    ("days", 18, "18 days"), ("days", 1, "1 day"), ("months", 4.5, "4.5 months"), ("months", 1.0, "1 month"),
    ("percent", 25, "25%"), ("count", 1200, "1,200"), ("date", "2027-08-31", "August 31, 2027"),
])
def test_fact_formatting_by_unit(unit, value, text):
    from backend.agent.ui.datasets import fmt
    assert fmt({"value": value, "unit": unit}) == text


def test_goal_and_monthly_facts_come_from_trusted_records(profile):
    facts = build_facts([result(profile, "savings")], {})
    w = profile.wellness_inputs
    assert facts["savings.goal_monthly_contribution"] == {
        "label": f"Monthly saving toward {profile.goal.name}", "value": profile.goal.monthly_contribution,
        "good": "up", "unit": "dollars"}
    assert facts["savings.goal_target_date"]["value"] == profile.goal.target_date.isoformat()
    assert facts["savings.goal_target_date"]["unit"] == "date"
    assert [facts[k]["value"] for k in ("monthly.income", "monthly.spending", "monthly.recurring_bills",
                                         "monthly.debt_payments", "liquid_cash")] == [
        w.monthly_income_avg, w.monthly_spending_avg, w.monthly_recurring_bills,
        w.scheduled_monthly_debt_payments, w.liquid_cash]
    assert all(f["unit"] == "dollars" for k, f in facts.items() if k != "savings.goal_target_date")


def test_non_dollar_facts_render_in_text_and_tiles(profile):
    savings = result(profile, "savings")
    facts = build_facts([savings], {})
    facts["other.days"] = {"label": "Days to reach goal", "value": 18, "good": "none", "unit": "days"}
    plan = UIPlan(answer="You'd get there in {other.days}, before {savings.goal_target_date}.",
                  stats=["other.days", "savings.goal_target_date", "savings.balance"])
    doc = validate_document(build_document(plan, {}, facts, []))
    target = profile.goal.target_date
    assert doc["blocks"][0]["props"]["text"] == (
        f"You'd get there in 18 days, before {target:%B} {target.day}, {target.year}.")
    days, when, balance = doc["blocks"][1]["props"]["items"]
    assert days == {"label": "Days to reach goal", "goodDirection": "none", "value": "18 days"}
    assert when["value"] == f"{target:%B} {target.day}, {target.year}" and "format" not in when
    assert balance["format"] == {"style": "currency", "decimals": 0}


# Calculate plan, step 5: calculations in the answer

DAYS = {"name": "days_needed", "label": "Days to reach goal", "unit": "days",
        "formula": "ceil({savings.goal_remaining} / 100)"}


def calc_state(profile, calculations, plan_output=None, planner_model=None):
    savings = result(profile, "savings")
    remaining = savings.data["goal_remaining"]
    calcs = [{**c, "value": -(-remaining // 100)} if c.get("value") == "auto" else c for c in calculations]
    model = planner_model or planner(plan_output)
    return remaining, gen_ui({"query": "If I add $100 a day, how fast can I get my car?", "results": [savings],
                              "calculations": calcs, "verify": VerifyDecision(done=True)}, model)


def test_cited_calculation_shows_value(profile):
    remaining, update = calc_state(profile, [{**DAYS, "value": "auto"}], {
        "answer": "At that pace you'd reach it in {calc.days_needed}.",
        "stats": ["calc.days_needed", "savings.goal_remaining"]})
    days = -(-remaining // 100)
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "stats", "bar_chart"]  # no formula explanation
    assert blocks[0]["props"]["text"] == f"At that pace you'd reach it in {days} days."
    assert blocks[1]["props"]["items"][0] == {"label": "Days to reach goal", "goodDirection": "none",
                                              "value": f"{days} days"}


def test_failed_calculations_become_caveats(profile):
    _, update = calc_state(profile, [{**DAYS, "value": "auto"},
                                     {**DAYS, "name": "bad", "label": "Weeks needed", "error": "Division by zero"}],
                           {"answer": "Here is your goal."})
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "bar_chart", "callout"]
    assert blocks[2]["props"]["text"] == "Couldn't calculate weeks needed: Division by zero."


def test_fallback_keeps_calculated_answer(profile):
    failing = Mock()
    failing.with_structured_output.return_value.invoke.side_effect = ConnectionError("down")
    remaining, update = calc_state(profile, [{**DAYS, "value": "auto"}], planner_model=failing)
    blocks = update["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "stats", "bar_chart"]
    assert blocks[1]["props"]["items"][0]["value"] == f"{-(-remaining // 100)} days"
    assert blocks[2]["props"]["title"] == "Key figures from this answer"  # the fallback's dollar tiles


def test_monthly_category_average_counts_every_month(profile):
    results = [result(profile, "transactions")]
    datasets = build_datasets(results)
    facts = build_facts(results, datasets)
    months = datasets["income_vs_spending"]["keys"]
    dining = sum(t.amount if t.direction == "out" else -t.amount for t in profile.transactions
                 if t.flow_class == "expense" and t.category == "dining")
    assert facts["spending.avg_monthly.dining"] == {"label": "Average monthly spending, Dining",
                                                    "value": round(dining / len(months)), "good": "down",
                                                    "unit": "dollars"}


def test_calculated_dollar_tiles_are_whole_dollars():
    from backend.agent.nodes.gen_ui import _tile
    assert _tile({"label": "Saved by Christmas", "value": 4922.79, "good": "none", "unit": "dollars"})["value"] == 4923


# Comparison bar charts from facts (what-if visuals)

CMP_FACTS = {
    "savings.goal_target": {"label": "Car fund target", "value": 6000, "good": "none", "unit": "dollars"},
    "calc.by_christmas": {"label": "Projected by Christmas", "value": 4922.79, "good": "none", "unit": "dollars"},
    "calc.days_now": {"label": "Days at current rate", "value": 135, "good": "none", "unit": "days"},
    "calc.days_new": {"label": "Days with $100/day", "value": 15.9, "good": "none", "unit": "days"},
    "savings.goal_target_date": {"label": "Target date", "value": "2027-12-31", "good": "none", "unit": "date"},
}


def test_fact_comparison_chart_uses_code_values():
    from backend.agent.nodes.gen_ui import build_document
    plan = UIPlan(answer="You'll be close.", charts=[
        {"facts": ["calc.by_christmas", "savings.goal_target"], "title": "Car fund by Christmas vs target",
         "highlight": ["Projected by Christmas", "Invented"]},
        {"facts": ["calc.days_now", "calc.days_new"], "title": "Days to reach the goal", "orientation": "horizontal"}])
    assert plan_problems(plan, CMP_FACTS, {}) == []
    money_chart, days_chart = [b["props"] for b in validate_document(build_document(plan, {}, CMP_FACTS, []))["blocks"][1:]]
    assert money_chart["categories"] == ["Projected by Christmas", "Car fund target"]
    assert money_chart["series"] == [{"name": "Amount", "values": [4923, 6000]}]
    assert money_chart["valueFormat"] == {"style": "currency", "decimals": 0}
    assert money_chart["highlight"] == ["Projected by Christmas"]
    assert days_chart["series"] == [{"name": "Days", "values": [135, 15.9]}]
    assert days_chart["valueFormat"] == {"style": "number", "decimals": 1, "suffix": " days"}


@pytest.mark.parametrize("charts,problem", [
    ([{"facts": ["calc.days_now", "savings.goal_target"], "title": "Mixed"}], "share one numeric unit"),
    ([{"facts": ["savings.goal_target_date", "calc.days_now"], "title": "Date"}], "share one numeric unit"),
    ([{"facts": ["calc.days_now", "made.up"], "title": "Unknown"}], "Unknown chart fact 'made.up'"),
])
def test_invalid_fact_charts_are_rejected(charts, problem):
    assert any(problem in p for p in plan_problems(UIPlan(answer="x", charts=charts), CMP_FACTS, {}))


@pytest.mark.parametrize("chart", [
    {"title": "Neither"},
    {"dataset": "income_vs_spending", "facts": ["a", "b"], "title": "Both"},
    {"facts": ["a"], "title": "One fact"},
    {"facts": ["a", "b", "c", "d", "e"], "title": "Five facts"},
])
def test_chart_choice_needs_exactly_one_source(chart):
    with pytest.raises(ValueError):
        UIPlan(answer="x", charts=[chart])


# Every answer with account data gets a chart, chosen by code when the plan has none


def test_answer_figures_are_charted_when_the_plan_has_no_chart(profile):
    from backend.agent.nodes.gen_ui import build_document
    facts = build_facts([result(profile, "savings")], {})
    facts["calc.months_now"] = {"label": "Months at your current rate", "value": 4.5, "good": "none", "unit": "months"}
    facts["calc.months_new"] = {"label": "Months with the extra income", "value": 0.6, "good": "none", "unit": "months"}
    doc = validate_document(build_document(
        UIPlan(answer="It takes {calc.months_now} now and {calc.months_new} with the extra income."), {}, facts, []))
    chart = doc["blocks"][1]["props"]
    assert doc["blocks"][1]["type"] == "bar_chart" and chart["title"] == "Key figures from this answer"
    assert chart["categories"] == ["Months at your current rate", "Months with the extra income"]
    assert chart["series"] == [{"name": "Months", "values": [4.5, 0.6]}]
    assert chart["valueFormat"] == {"style": "number", "decimals": 1, "suffix": " months"}


def test_spending_and_average_month_defaults(profile):
    from backend.agent.nodes.gen_ui import build_document
    checking = [result(profile, "checking")]
    datasets = build_datasets(checking)
    doc = validate_document(build_document(UIPlan(answer="Here you go."), datasets, build_facts(checking, datasets), []))
    chart = doc["blocks"][1]["props"]
    assert chart["title"] == datasets["spending_by_category.2026-10"]["description"] and chart["sort"] == "desc"
    assert chart["series"] == datasets["spending_by_category.2026-10"]["series"]
    loans = [result(profile, "loans")]  # loan records have no spending, and no savings goal
    doc = validate_document(build_document(UIPlan(answer="Here you go."), build_datasets(loans),
                                           build_facts(loans, {}), []))
    w = profile.wellness_inputs
    assert doc["blocks"][1]["props"]["title"] == "Your average month"
    assert doc["blocks"][1]["props"]["series"][0]["values"] == [
        w.monthly_income_avg, w.monthly_spending_avg, w.monthly_recurring_bills, w.scheduled_monthly_debt_payments]


def test_plan_chart_is_not_duplicated_and_no_data_means_no_chart(profile):
    from backend.agent.nodes.gen_ui import build_document
    results = [result(profile, "transactions")]
    datasets = build_datasets(results)
    plan = UIPlan(answer="Here.", charts=[{"dataset": "income_vs_spending", "title": "Income and spending"}])
    blocks = build_document(plan, datasets, build_facts(results, datasets), [])["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "bar_chart"]
    update = gen_ui({"query": "What's the weather?", "results": [],
                     "verify": VerifyDecision(done=False, missing="This is not a banking question.")})
    assert "bar_chart" not in [b["type"] for b in update["final_ui"]["blocks"]]  # nothing real to chart
