from datetime import date

import pytest

from backend.agent.calc import CalcError, evaluate, question_numbers, run_all

AS_OF = date(2026, 10, 31)
FACTS = {
    "savings.goal_remaining": {"value": 1800, "unit": "dollars"},
    "savings.goal_monthly_contribution": {"value": 150, "unit": "dollars"},
    "savings.goal_target_date": {"value": "2027-08-31", "unit": "date"},
    "spending_by_category.2026-10.spent.dining": {"value": 149, "unit": "dollars"},
    "zero": {"value": 0, "unit": "dollars"},
}
CAR = "If I add $100 a day for the next month, how much more quickly can I get my car?"


def ev(formula, question=CAR, earlier=None):
    return evaluate(formula, FACTS, question, AS_OF, earlier)


def test_screenshot_question():
    assert ev("ceil({savings.goal_remaining} / 100)") == 18
    assert ev("ceil({savings.goal_remaining} / {savings.goal_monthly_contribution})") == 12
    assert ev("100 * 30") == 3000


def test_operators_and_functions():
    assert ev("-{savings.goal_remaining} + 100") == -1700
    assert ev("+(100 - 30) // 7") == 10
    assert ev("min(100, 30, 7)") == 7 and ev("max(0, 100 - {savings.goal_remaining})") == 0
    assert ev("abs(30 - 100)") == 70 and ev("floor(100 / 7)") == 14 and ev("round(100 / 7)") == 14
    assert ev("{savings.goal_remaining} / 7") == pytest.approx(257.142857)


def test_number_grounding():
    assert question_numbers("Save $1,500 or 10% by 2027?") == {1500.0, 10.0, 2027.0}
    assert ev("{savings.goal_remaining} - 1500", "What if I spend $1,500?") == 300
    assert ev("{spending_by_category.2026-10.spent.dining} * 0.5", "What if I cut dining in half?") == 74.5
    with pytest.raises(CalcError, match="Number 250 is not in the question"):
        ev("{savings.goal_remaining} / 250")


@pytest.mark.parametrize("formula", [
    "__import__('os').system('ls')", "().__class__", "{savings.goal_remaining}.real", "100 ** 2",
    "100 if 1 else 30", "(lambda: 1)()", "[x for x in (1, 2)]", "max(1, 2, key=abs)", "round(100 / 7, 2)",
    "True + 1", "'abc'", "100 < 30", "open('x')",
])
def test_disallowed_syntax(formula):
    with pytest.raises(CalcError):
        ev(formula)


def test_unknown_facts_and_names():
    with pytest.raises(CalcError, match=r"Unknown fact \{made.up\}"):
        ev("{made.up} + 1")
    with pytest.raises(CalcError, match="Unknown name days_needed"):
        ev("days_needed * 2")
    assert ev("days_needed * 2", earlier={"days_needed": 18}) == 36


def test_dates_count_from_data_date():
    assert ev('days_until("2026-12-25")', "Can I afford it by Christmas?") == 55
    assert ev('months_until("2026-12-25")', "By Christmas?") == pytest.approx(55 * 12 / 365.25)
    assert ev("days_until({savings.goal_target_date})") == 304
    for bad in ('days_until("2026-10-01")', 'days_until("2040-01-01")', 'days_until("Christmas")',
                "days_until(100)", "{savings.goal_target_date} + 1", "{savings.goal_target_date}"):
        with pytest.raises(CalcError):
            ev(bad)


def test_limits_and_math_errors():
    with pytest.raises(CalcError, match="Division by zero"):
        ev("{savings.goal_remaining} / {zero}")
    with pytest.raises(CalcError, match="longer than"):
        ev("1 + " * 60 + "1")
    with pytest.raises(CalcError, match="not a usable number"):
        ev("365 * 365 * 365 * 365")
    with pytest.raises(CalcError, match="not valid arithmetic"):
        ev("100 +")


def test_run_all_chains_and_isolates_failures():
    calcs = [
        {"name": "extra", "label": "Extra saved", "unit": "dollars", "formula": "100 * 30"},
        {"name": "broken", "label": "Broken", "unit": "days", "formula": "{savings.goal_remaining} / {zero}"},
        {"name": "days_needed", "label": "Days to goal", "unit": "days",
         "formula": "ceil({savings.goal_remaining} / (extra / 30))"},
    ]
    out = run_all(calcs, FACTS, CAR, AS_OF)
    assert out[0]["value"] == 3000 and out[1]["error"] == "Division by zero" and "value" not in out[1]
    assert out[2] == {**calcs[2], "value": 18}
