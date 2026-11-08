import backend  # noqa: F401
from wellness.metrics import compute_metrics


def test_spending_counts_card_purchases_once(primary):
    p, u = primary.profile, primary.unified
    expenses = sum(t.amount for t in p.transactions if t.flow_class == "expense")
    assert sum(m.spending for m in u.monthly_summary) == expenses
    card_payments = sum(t.amount for t in p.transactions
                        if t.account_type == "credit_card" and t.transaction_type == "payment")
    assert card_payments > 0  # exist, but are not in spending
    assert sum(m.debt_payments for m in u.monthly_summary) == card_payments + sum(
        t.amount for t in p.transactions if t.account_type in {"student_loan", "auto_loan"}
        and t.transaction_type == "payment")


def test_transfers_never_income(bundles):
    for b in bundles:
        income = sum(t.amount for t in b.profile.transactions if t.flow_class == "income")
        assert sum(m.income for m in b.unified.monthly_summary) == income


def test_net_cash_flow_matches_liquid_change(bundles):
    for b in bundles:
        u = b.unified
        liquid_open = sum(a.opening_balance for a in u.accounts if a.type in {"checking", "savings"})
        interest = sum(m.asset_interest for m in u.monthly_summary)
        assert liquid_open + sum(m.net_cash_flow for m in u.monthly_summary) + interest == u.wellness_inputs.liquid_cash


def test_sources_tagged(primary):
    u = primary.unified
    assert u.user.sources["first_name"].value == "waypoint_generated"
    pnc_only = [t for t in u.transactions if t.nessie_local_key is None]
    assert pnc_only and all(t.source.note for t in pnc_only)
    assert all(t.nessie_resource for t in u.transactions if t.nessie_local_key)


def test_pnc_compute_metrics_runs_on_unified_view(bundles):
    for b in bundles:
        out = compute_metrics(b.unified.pnc_view)
        assert out["values"]["debt_to_income"] is not None
        assert set(out["status"]) >= {"emergency_fund_months", "savings_rate", "credit_utilization"}
