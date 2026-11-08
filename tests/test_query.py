from datetime import date

import pytest

from backend.agent.calc import CalcError, evaluate
from backend.agent.nodes.calculate import calculate
from backend.agent.nodes.gen_ui import gen_ui
from backend.agent.query import run_query
from backend.agent.schemas import ProductResult, Query, VerifyDecision
from backend.agent.ui.datasets import build_facts

T = [  # merchant, category, direction, amount, date
    {"transaction_id": "1", "merchant_name": "Starbucks", "description": "", "category": "coffee", "account_type": "checking",
     "direction": "out", "flow_class": "expense", "amount": 6, "date": "2026-09-03"},
    {"transaction_id": "2", "merchant_name": "Starbucks", "description": "", "category": "coffee", "account_type": "checking",
     "direction": "out", "flow_class": "expense", "amount": 9, "date": "2026-09-20"},
    {"transaction_id": "3", "merchant_name": "Starbucks", "description": "", "category": "coffee", "account_type": "checking",
     "direction": "out", "flow_class": "expense", "amount": 7, "date": "2026-10-02"},
    {"transaction_id": "4", "merchant_name": "Campus Grill", "description": "", "category": "dining", "account_type": "checking",
     "direction": "out", "flow_class": "expense", "amount": 40, "date": "2026-09-10"},
    {"transaction_id": "5", "merchant_name": None, "description": "Payroll", "category": "payroll", "account_type": "checking",
     "direction": "in", "flow_class": "income", "amount": 600, "date": "2026-09-15"},
]


def q(**kw):
    return Query(name="q", label="Result", **kw).model_dump()


def test_query_filters_and_aggregates_in_code():
    sept = {"date_from": "2026-09-01", "date_to": "2026-09-30"}
    assert run_query(q(merchant="starbucks", **sept), T)["value"] == 15  # case-insensitive, date range
    assert run_query(q(merchant="starbucks", aggregate="count"), T) | {} == {
        "name": "q", "label": "Result", "unit": "count", "value": 3, "query": True,
        "formula": "count of transactions where merchant starbucks"}
    assert run_query(q(direction="out", aggregate="max"), T)["value"] == 40
    assert run_query(q(category="coffee", aggregate="average"), T)["value"] == pytest.approx(22 / 3)
    top = run_query(q(direction="out", aggregate="top", group_by="merchant"), T)
    assert top["items"] == [("Campus Grill", 40), ("Starbucks", 22)] and top["value"] == 40
    assert run_query(q(merchant="nowhere"), T)["value"] == 0
    assert run_query(q(merchant="nowhere", aggregate="min"), T)["error"] == "No matching transactions"
    with pytest.raises(ValueError):
        Query(name="q", label="x", date_from="Sept 1")


def test_queries_run_before_formulas_and_feed_charts():
    data = {"accounts": [{"balance": 500, "apr_pct": 0}], "balance_total": 500, "transactions": T, "as_of_date": "2026-10-31"}
    results = [ProductResult(product="checking", data=data, summary="ok", confidence=1)]
    decision = VerifyDecision(done=False, missing="Coffee spend", queries=[
        Query(name="coffee_sept", label="Coffee in September", merchant="starbucks", date_to="2026-09-30"),
        Query(name="top_spend", label="Top merchants", direction="out", aggregate="top")],
        calculations=[{"name": "per_week", "label": "Per week", "unit": "dollars", "formula": "coffee_sept / 2"}])
    out = {c["name"]: c for c in calculate({"query": "How much on Starbucks?", "results": results, "calculations": [],
                                             "verify": decision})["calculations"]}
    assert out["coffee_sept"]["value"] == 15 and out["per_week"]["value"] == 7.5
    model_plan = {"blocks": [{"type": "paragraph", "size": "lead", "text": "You spent {calc.coffee_sept}."},
                             {"type": "bar_chart", "dataset": "query.top_spend", "title": "Where it went"}]}
    from test_gen_ui import planner
    blocks = gen_ui({"query": "x", "results": results, "calculations": list(out.values()),
                     "verify": VerifyDecision(done=True)}, planner(model_plan))["final_ui"]["blocks"]
    assert blocks[0]["props"]["text"] == "You spent $15." and blocks[1]["props"]["series"][0]["values"] == [40, 22]


def test_bill_and_rate_facts():
    data = {"accounts": [{"balance": 900, "apr_pct": 6.8, "monthly_payment": 110}], "balance_total": 900,
            "bills": [{"bill_key": "b1", "payee": "Verizon", "amount": 35, "next_due_date": "2026-11-10", "status": "recurring"}]}
    facts = build_facts([ProductResult(product="loans", data=data, summary="ok", confidence=1)], {})
    assert facts["loans.apr"]["value"] == 6.8 and facts["loans.apr"]["unit"] == "percent"
    assert facts["loans.monthly_payment"]["value"] == 110 and facts["bills.monthly_total"]["value"] == 35
    assert facts["bill.verizon.next_due"] == {"label": "Verizon next due date", "value": "2026-11-10", "good": "none",
                                              "unit": "date"}
    # Loan payoff months with real interest: n = -log(1 - r*B/P) / log(1 + r)
    months = evaluate("ceil(-log(1 - ({loans.apr} / 100 / 12) * {loans.balance} / {loans.monthly_payment})"
                      " / log(1 + {loans.apr} / 100 / 12))", facts, "When is my loan paid off?", date(2026, 10, 31))
    assert months == 9
    with pytest.raises(CalcError):
        evaluate("log(0)", facts, "", date(2026, 10, 31))
