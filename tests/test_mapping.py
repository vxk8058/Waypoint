from backend.mapping.missing_fields import generate_missing_fields
from backend.mapping.pnc_to_nessie import build_seed_plan, next_occurrence
from backend.schemas.common import Origin
from backend.schemas.nessie import REF_PREFIX
from datetime import date


def test_plan_deterministic(primary):
    again = build_seed_plan(primary.profile, generate_missing_fields(primary.profile))
    assert again.model_dump() == primary.plan.model_dump()


def test_resource_order(primary):
    resources = [op.resource for op in primary.plan.operations]
    assert resources[0] == "customer"
    last_setup = max(i for i, r in enumerate(resources) if r in {"merchant", "account", "loan", "bill"})
    first_txn = min(i for i, r in enumerate(resources) if r in {"deposit", "withdrawal", "purchase", "transfer"})
    assert last_setup < first_txn


def test_account_balances_are_closing_balances(primary):
    accounts = {a.account_id: a for a in primary.profile.accounts}
    for op in primary.plan.operations:
        if op.resource == "account":
            assert op.body["balance"] == accounts[op.source_record_id].balance
            assert op.marker in op.body["nickname"]


def test_loans_attach_to_checking(primary):
    loans = [op for op in primary.plan.operations if op.resource == "loan"]
    assert loans and all(op.parent_key.endswith("-checking") for op in loans)


def test_transfer_bodies_have_only_live_api_fields(bundles):
    for b in bundles:
        for op in b.plan.operations:
            if op.resource == "transfer":
                assert set(op.body) == {"transaction_date", "status", "amount", "description"}


def test_purchases_use_purchase_date_and_merchant_ref(primary):
    purchases = [op for op in primary.plan.operations if op.resource == "purchase"]
    assert purchases
    for op in purchases:
        assert "purchase_date" in op.body and "transaction_date" not in op.body
        assert op.body["merchant_id"] == REF_PREFIX + op.refs["merchant_id"]


def test_non_cash_and_loan_rows_are_skipped(bundles):
    for b in bundles:
        planned = {op.source_record_id for op in b.plan.operations}
        for t in b.profile.transactions:
            if t.flow_class == "non_cash" or t.account_type in {"student_loan", "auto_loan"}:
                assert t.transaction_id not in planned


def test_every_transaction_planned_or_skipped_once(bundles):
    for b in bundles:
        planned = {op.source_record_id for op in b.plan.operations if op.resource in
                   {"deposit", "withdrawal", "purchase", "transfer"}}
        skipped = {s.record_id for s in b.plan.skipped}
        assert planned.isdisjoint(skipped)
        assert planned | skipped == {t.transaction_id for t in b.profile.transactions}


def test_missing_fields_sources_and_rewards(primary):
    gen = primary.generated
    assert gen.field_sources["customer.first_name"] == Origin.WAYPOINT_GENERATED
    card = primary.profile.account_of_type("credit_card")
    spent = sum(t.amount for t in primary.profile.transactions
                if t.account_id == card.account_id and t.transaction_type == "purchase")
    assert gen.account_rewards[card.account_id] == spent
    assert gen.customer.city == primary.profile.student.city


def test_next_occurrence():
    assert next_occurrence(date(2026, 10, 31), 1) == date(2026, 11, 1)
    assert next_occurrence(date(2026, 10, 10), 15) == date(2026, 10, 15)
    assert next_occurrence(date(2026, 12, 20), 5) == date(2027, 1, 5)
