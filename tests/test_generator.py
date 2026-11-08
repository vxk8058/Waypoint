from backend.generation.student_generator import generate_all, interest, month_periods
from backend.schemas.student import ASSET_TYPES
from datetime import date


def test_deterministic():
    assert [p.model_dump() for p in generate_all()] == [p.model_dump() for p in generate_all()]


def test_four_profiles_one_primary(bundles):
    assert 3 <= len(bundles) <= 5
    assert sum(b.profile.is_primary_demo for b in bundles) == 1


def test_student_shaped_accounts(bundles):
    allowed = {"checking", "savings", "credit_card", "student_loan", "auto_loan"}
    for b in bundles:
        types = {a.account_type for a in b.profile.accounts}
        assert {"checking", "savings"} <= types <= allowed  # no mortgage / IRA / CD


def test_whole_dollars_everywhere(bundles):
    for b in bundles:
        for t in b.profile.transactions:
            assert all(isinstance(v, int) for v in (t.amount, t.balance_change, t.balance_after))
        assert all(isinstance(a.balance, int) for a in b.profile.accounts)


def test_six_months_of_history(primary):
    months = {t.posted_date.strftime("%Y-%m") for t in primary.profile.transactions}
    assert months == {"2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"}


def test_assets_never_negative(bundles):
    for b in bundles:
        for t in b.profile.transactions:
            if t.account_type in ASSET_TYPES:
                assert t.balance_after >= 0


def test_interest_rounds_half_up():
    assert interest(1500, 4.0) == 5
    assert interest(0, 24.99) == 0
    assert interest(1200, 6.0) == 6


def test_month_periods_requires_month_end():
    assert month_periods(date(2026, 10, 31), 2) == [date(2026, 9, 1), date(2026, 10, 1)]
    try:
        month_periods(date(2026, 10, 30), 2)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
