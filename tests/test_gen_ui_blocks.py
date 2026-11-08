"""Rich answer layouts: every block type, rows, stat changes, projections — numbers still only from code."""
import statistics

import pytest

from backend.agent.nodes.gen_ui import build_document, gen_ui
from backend.agent.schemas import VerifyDecision
from backend.agent.ui.components import validate_document
from backend.agent.ui.datasets import build_datasets, build_facts
from backend.agent.ui.plan import UIPlan
from backend.agent.ui.validate import plan_problems
from test_gen_ui import planner, result


@pytest.fixture
def world(primary):
    profile = primary.unified.model_copy(deep=True)
    results = [result(profile, "savings"), result(profile, "checking"), result(profile, "credit_card")]
    datasets = build_datasets(results)
    facts = build_facts(results, datasets)
    facts["calc.extra_total"] = {"label": "Extra saved", "value": 3000, "good": "none", "unit": "dollars"}
    return profile, results, datasets, facts


def test_rich_layout_builds_every_block_type(world):
    profile, _, datasets, facts = world
    plan = UIPlan(blocks=[
        {"type": "heading", "text": "Your October in review", "level": 1},
        {"type": "paragraph", "size": "small", "tone": "muted", "text": "Based on your records."},
        {"type": "paragraph", "size": "lead",
         "text": "You spent **{income_vs_spending.spending.2026-10}** in October."},
        {"type": "stats", "stats": [
            {"fact": "income_vs_spending.spending.2026-10", "compare_to": "income_vs_spending.spending.2026-09",
             "caption": "vs. September"},
            {"fact": "savings.goal_saved", "caption": "toward your goal"}]},
        {"type": "bar_chart", "dataset": "spending_by_category.2026-10", "title": "Spending by category",
         "subtitle": "October", "orientation": "horizontal", "sort": "desc", "highlight": ["Dining"]},
        {"type": "heading", "text": "Side by side", "level": 2},
        {"type": "line_chart", "dataset": "goal_projection", "title": "Projected savings"},
        {"type": "histogram", "dataset": "transaction_sizes", "title": "Transaction sizes",
         "subtitle": "{transaction_sizes.count} transactions", "markers": ["mean", "median"], "beside_previous": True},
        {"type": "callout", "tone": "warning", "title": "Dining is the one to watch", "text": "Keep an eye on it."},
        {"type": "pie_chart", "dataset": "spending_by_category.2026-10", "title": "Where October went"},
        {"type": "divider"},
        {"type": "list", "items": ["Review subscriptions", "Keep saving **{savings.goal_monthly_contribution}**"]},
    ])
    assert plan_problems(plan, facts, datasets) == []
    blocks = validate_document(build_document(plan, datasets, facts, []))["blocks"]
    assert [b["type"] for b in blocks] == ["heading", "paragraph", "paragraph", "stats", "bar_chart", "heading", "row",
                                           "callout", "pie_chart", "divider", "list"]
    assert blocks[1]["props"] == {"text": "Based on your records.", "size": "small", "tone": "muted"}
    spend = facts["income_vs_spending.spending.2026-10"]["value"]
    before = facts["income_vs_spending.spending.2026-09"]["value"]
    assert blocks[2]["props"] == {"text": f"You spent **${spend:,}** in October.", "size": "lead"}
    tile = blocks[3]["props"]["items"][0]
    assert tile["change"] == round((spend - before) / before * 100, 1) and tile["caption"] == "vs. September"
    assert blocks[4]["props"]["subtitle"] == "October" and blocks[4]["props"]["highlight"] == ["Dining"]
    line, histogram = blocks[6]["props"]["blocks"]
    assert line["type"] == "line_chart" and histogram["type"] == "histogram"
    sizes = datasets["transaction_sizes"]["values"]
    assert histogram["props"]["values"] == sizes and histogram["props"]["markers"] == ["mean", "median"]
    assert histogram["props"]["subtitle"] == f"{len(sizes)} transactions"
    assert blocks[7]["props"] == {"tone": "warning", "title": "Dining is the one to watch", "text": "Keep an eye on it."}
    october = datasets["spending_by_category.2026-10"]
    assert blocks[8]["props"]["data"] == [{"label": c, "value": v}
                                          for c, v in zip(october["categories"], october["series"][0]["values"])]
    assert blocks[10]["props"]["items"][1] == f"Keep saving **${profile.goal.monthly_contribution:,}**"
    assert statistics.median(sizes) == facts["transaction_sizes.median"]["value"]


def test_goal_projection_with_and_without_what_if(world):
    profile, _, datasets, facts = world
    goal, ds = profile.goal, datasets["goal_projection"]
    assert ds["history"][-1] == goal.current_saved
    current = build_document(UIPlan(blocks=[{"type": "line_chart", "dataset": "goal_projection"}]),
                             datasets, facts, [])["blocks"][0]["props"]
    steps = -(-(goal.target_amount - goal.current_saved) // goal.monthly_contribution)
    assert current["series"][0]["values"] == ds["history"] + [
        min(goal.target_amount, goal.current_saved + goal.monthly_contribution * k) for k in range(1, steps + 1)]
    assert current["forecastFrom"] == "2026-10" and current["x"][len(ds["keys"])] == "2026-11"
    assert current["referenceLines"] == [{"value": goal.target_amount, "label": f"{goal.name} goal"}]
    what_if = validate_document(build_document(UIPlan(blocks=[
        {"type": "line_chart", "dataset": "goal_projection", "lump_sum": "calc.extra_total",
         "scenario_name": "With the extra income"}]), datasets, facts, []))["blocks"][0]["props"]
    saved, scenario = what_if["series"]
    assert scenario["name"] == "With the extra income"
    history = len(ds["keys"])
    assert scenario["values"][:history] == [None] * (history - 1) + [goal.current_saved]
    assert scenario["values"][history] == min(goal.target_amount, goal.current_saved + goal.monthly_contribution + 3000)
    assert len(saved["values"]) == len(scenario["values"]) == len(what_if["x"])


def test_rows_hold_at_most_three(world):
    _, _, datasets, facts = world
    chart = {"type": "bar_chart", "facts": ["savings.goal_saved", "savings.goal_target"], "beside_previous": True}
    charts = [{**chart, "title": title} for title in ("One", "Two", "Three", "Four")]
    charts[0]["beside_previous"] = False
    blocks = build_document(UIPlan(blocks=charts), datasets, facts, [])["blocks"]
    assert [b["type"] for b in blocks] == ["row", "bar_chart"] and len(blocks[0]["props"]["blocks"]) == 3
    validate_document({"blocks": blocks})


@pytest.mark.parametrize("block,problem", [
    ({"type": "pie_chart", "dataset": "income_vs_spending"}, "can't draw the time dataset"),
    ({"type": "histogram", "dataset": "spending_by_category.2026-10"}, "can't draw the category dataset"),
    ({"type": "line_chart"}, "needs a dataset"),
    ({"type": "line_chart", "dataset": "goal_projection", "extra_monthly": "transaction_sizes.count"},
     "What-if amounts must be dollar facts"),
    ({"type": "bar_chart", "dataset": "income_vs_spending", "lump_sum": "calc.extra_total"},
     "What-if amounts must be dollar facts"),
    ({"type": "list"}, "A list needs items"),
    ({"type": "heading"}, "A heading needs text"),
    ({"type": "stats", "stats": [{"fact": "savings.goal_saved", "compare_to": "transaction_sizes.count"}]},
     "same numeric unit"),
    ({"type": "list", "items": ["Save 200 dollars"]}, "not digits"),
    ({"type": "callout", "text": "Hi", "title": "Over by {made.up}"}, "Unknown fact placeholder"),
])
def test_block_problems(world, block, problem):
    _, _, datasets, facts = world
    assert any(problem in p for p in plan_problems(UIPlan(blocks=[block]), facts, datasets))


def test_bad_blocks_are_dropped_after_regeneration(world):
    _, results, _, _ = world
    plan = {"blocks": [{"type": "paragraph", "size": "lead", "text": "Here is your month."},
                       {"type": "list", "items": ["Cut 100 dollars"]},
                       {"type": "pie_chart", "dataset": "spending_by_category.2026-10", "title": "Where it went"}]}
    model = planner(plan, plan)
    blocks = gen_ui({"query": "How was October?", "results": results, "verify": VerifyDecision(done=True)},
                    model)["final_ui"]["blocks"]
    assert model.with_structured_output.return_value.invoke.call_count == 2
    assert [b["type"] for b in blocks] == ["paragraph", "pie_chart"]  # the bad list is dropped, the rest kept
    assert "100" not in str(blocks[:2])


def test_model_slips_are_repaired(world):
    """Live runs showed text written in "title" and placeholders written without braces."""
    profile, _, datasets, facts = world
    plan = UIPlan(blocks=[
        {"type": "heading", "level": 1, "title": "Your car fund"},
        {"type": "paragraph", "size": "lead", "title": "You've saved **savings.goal_saved** of savings.goal_target."},
        {"type": "callout", "tone": "info", "title": "Keep going"},
        {"type": "line_chart", "dataset": "income_vs_spending"},
    ])
    assert plan_problems(plan, facts, datasets) == []
    blocks = validate_document(build_document(plan, datasets, facts, []))["blocks"]
    goal = profile.goal
    assert blocks[0]["props"] == {"text": "Your car fund", "level": 1}
    assert blocks[1]["props"]["text"] == f"You've saved **${goal.current_saved:,}** of ${goal.target_amount:,}."
    assert blocks[2]["props"] == {"tone": "info", "text": "Keep going"}
    assert blocks[3]["props"]["title"] == datasets["income_vs_spending"]["description"]  # untitled chart
    bare_with_digits = UIPlan(blocks=[{"type": "paragraph", "text": "October: income_vs_spending.spending.2026-10"}])
    assert plan_problems(bare_with_digits, facts, datasets) == []  # digits inside a known key aren't typed numbers


def test_stat_change_only_compares_the_same_measure_across_months(world):
    _, _, datasets, facts = world
    plan = UIPlan(blocks=[{"type": "stats", "stats": [
        {"fact": "savings.goal_saved", "compare_to": "savings.goal_target", "caption": "vs target"},
        {"fact": "income_vs_spending.income.2026-10", "compare_to": "income_vs_spending.income.2026-09"}]}])
    saved, income = build_document(plan, datasets, facts, [])["blocks"][0]["props"]["items"]
    assert "change" not in saved and saved["caption"] == "vs target"  # saved vs target isn't a change over time
    now, before = facts["income_vs_spending.income.2026-10"]["value"], facts["income_vs_spending.income.2026-09"]["value"]
    assert income["change"] == round((now - before) / before * 100, 1)


def test_empty_layout_reply_gets_a_second_attempt(world):
    _, results, _, _ = world
    model = planner(ConnectionError("empty structured reply"),
                    {"blocks": [{"type": "paragraph", "size": "lead", "text": "Here is your month."},
                                {"type": "bar_chart", "dataset": "spending_by_category.2026-10", "title": "**Spending**"}]})
    blocks = gen_ui({"query": "How was October?", "results": results, "verify": VerifyDecision(done=True)},
                    model)["final_ui"]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "bar_chart"] and blocks[1]["props"]["title"] == "Spending"


def test_repeated_blocks_and_extra_callouts_are_dropped(world):
    _, _, datasets, facts = world
    callout = {"type": "callout", "tone": "info", "text": "Same note"}
    plan = UIPlan(blocks=[{"type": "paragraph", "text": "Lead."}] + [callout] * 50
                  + [{"type": "callout", "tone": "warning", "text": "Second"}, {"type": "callout", "text": "Third"}]
                  + [{"type": "paragraph", "text": f"Note {chr(97 + i % 26)}{i // 26}x"} for i in range(30)])
    assert "maxItems" in str(UIPlan.model_json_schema())
    blocks = build_document(plan, datasets, facts, [])["blocks"]
    assert [b["props"].get("text") for b in blocks[:3]] == ["Lead.", "Same note", "Second"]
    assert sum(b["type"] == "callout" for b in blocks) == 2
    assert len([b for b in blocks if b["type"] != "bar_chart"]) == 12  # capped (a default chart is added)


def test_live_formatting_slips_are_tidied(world):
    profile, _, datasets, facts = world
    from backend.agent.ui.validate import fill
    saved = f"${profile.goal.current_saved:,}"
    assert fill("Save **{savings.goal_saved}} a month", facts) == f"Save **{saved}** a month"
    assert fill("Saved **{savings.goal_saved} so far", facts) == f"Saved {saved} so far"  # dangling bold removed
    assert fill("Saved {{savings.goal_saved}}", facts) == f"Saved {saved}"
    blocks = build_document(UIPlan(blocks=[
        {"type": "paragraph", "size": "lead", "tone": "muted", "text": "Lead."},
        {"type": "stats", "stats": [{"fact": "savings.goal_saved", "caption": facts["savings.goal_saved"]["label"].upper()}]},
    ]), datasets, facts, [])["blocks"]
    assert blocks[0]["props"] == {"text": "Lead.", "size": "lead"}
    assert "caption" not in blocks[1]["props"]["items"][0]  # a caption that repeats the label adds nothing


@pytest.mark.parametrize("text,bad", [
    ("Reach it in {savings.goal_remaining} days", True),       # a dollar amount used as a number of days
    ("About **{savings.goal_remaining}** months sooner", True),
    ("It takes {calc.days} days", False),                      # repeated unit: removed when filled
    ("It takes {calc.days} months", True),                     # a number of days isn't months
    ("Save {savings.goal_remaining} a month", False),
    ("Save {savings.goal_monthly_contribution} per month", False),
    ("It takes {calc.days}", False),
])
def test_placeholder_followed_by_a_time_unit(world, text, bad):
    _, _, datasets, facts = world
    facts = {**facts, "calc.days": {"label": "Days", "value": 18, "good": "none", "unit": "days"}}
    problems = plan_problems(UIPlan(blocks=[{"type": "paragraph", "text": text}]), facts, datasets)
    assert bool(problems) is bad


def test_repeated_unit_after_a_placeholder_is_removed(world):
    from backend.agent.ui.validate import fill
    _, _, _, facts = world
    facts = {**facts, "calc.days": {"label": "Days", "value": 18, "good": "none", "unit": "days"},
             "calc.months": {"label": "Months", "value": 1, "good": "none", "unit": "months"}}
    assert fill("Done in **{calc.days}** days, or {calc.months} month.", facts) == "Done in **18 days**, or 1 month."


def test_numbers_from_the_question_may_be_restated(world):
    _, _, datasets, facts = world
    question = "If I earn $100 a day for the next 30 days, how much faster do I reach my goal?"
    ok = UIPlan(blocks=[{"type": "paragraph", "text": "Earning $100 a day for 30 days gets you there faster."}])
    assert plan_problems(ok, facts, datasets, question) == []
    invented = UIPlan(blocks=[{"type": "paragraph", "text": "Earning $100 a day saves $250."}])
    assert plan_problems(invented, facts, datasets, question)  # 250 isn't the user's number or a fact
