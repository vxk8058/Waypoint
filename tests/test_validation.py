from backend.validation.profile_validator import validate_profile


def _checks(report):
    return {e.check for e in report.errors}


def test_all_profiles_valid(bundles):
    for b in bundles:
        assert b.report.ok, b.report.errors


def test_detects_broken_ledger(primary):
    p = primary.profile.model_copy(deep=True)
    p.transactions[5].balance_change += 7
    assert "ledger_reconciliation" in _checks(validate_profile(p))


def test_detects_unpaired_transfer(primary):
    p = primary.profile.model_copy(deep=True)
    leg = next(t for t in p.transactions if t.flow_class == "internal_transfer")
    p.transactions = [t for t in p.transactions if t is not leg]
    assert "transfer_pairs" in _checks(validate_profile(p))


def test_detects_card_payment_counted_as_spending(primary):
    p = primary.profile.model_copy(deep=True)
    pay = next(t for t in p.transactions if t.account_type == "credit_card" and t.transaction_type == "payment")
    pay.flow_class = "expense"
    assert "flow_class_rules" in _checks(validate_profile(p))


def test_detects_goal_larger_than_savings(primary):
    p = primary.profile.model_copy(deep=True)
    p.goal.current_saved = p.account(p.goal.linked_account_id).balance + 1
    assert "goal_consistency" in _checks(validate_profile(p))


def test_detects_bill_amount_mismatch(primary):
    p = primary.profile.model_copy(deep=True)
    t = next(t for t in p.transactions if t.bill_key)
    t.amount += 1
    assert "bill_payments" in _checks(validate_profile(p))


def test_detects_assumption_drift(primary):
    p = primary.profile.model_copy(deep=True)
    p.assumptions.monthly_income *= 2
    assert "assumptions_vs_observed" in _checks(validate_profile(p))


def test_detects_bad_seed_plan_body(primary):
    plan = primary.plan.model_copy(deep=True)
    op = next(o for o in plan.operations if o.resource == "transfer")
    op.body["payee_id"] = "x"  # rejected by the live Nessie API
    assert "seed_plan_bodies" in _checks(validate_profile(primary.profile, plan))
