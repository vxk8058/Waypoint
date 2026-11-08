"""Map a PNC-convention student profile to a Nessie seed plan (no network calls).

Mapping rules (see docs/DATA_MAPPING.md):
- checking/savings/credit_card -> Nessie Account (balance = closing balance, because
  Nessie transactions never move balances and balances cannot be updated later).
- student_loan/auto_loan       -> Nessie Loan attached to the checking account.
- income rows                  -> Deposit
- expense rows with a merchant -> Purchase (checking or card)
- expense rows for bills/cash  -> Withdrawal
- internal transfer legs       -> Transfer on each Nessie account involved (Nessie transfers
  carry no destination, so each leg is recorded on its own account; the pairing lives in
  Waypoint via transfer_id).
- non_cash rows (interest)     -> not sent; kept in Waypoint (PNC-only).
- rows on loan accounts        -> not sent; Nessie loans have no transaction history.
- recurring bills              -> Bill (status "recurring") on the paying account.
"""
import calendar
from datetime import date

from ..schemas.common import Origin
from ..schemas.nessie import CREATE_MODELS, REF_PREFIX
from ..schemas.seed_plan import SeedOperation, SeedPlan, SkippedRecord
from ..schemas.student import LOAN_TYPES, StudentProfile, Transaction
from .missing_fields import GeneratedFields

NESSIE_ACCOUNT_TYPES = {"checking": "Checking", "savings": "Savings", "credit_card": "Credit Card"}


def marker(*parts: str) -> str:
    return "[wp:" + ":".join(parts) + "]"


def account_key(profile_id: str, account_id: str) -> str:
    return f"{profile_id}:account:{account_id}"


def merchant_local_key(mkey: str) -> str:
    # Merchants are global in Nessie and cannot be deleted, so they are shared across profiles.
    return f"merchant:{mkey}"


def next_occurrence(after: date, day: int) -> date:
    year, month = after.year, after.month
    if after.day >= day:
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def classify_transaction(t: Transaction) -> str | None:
    """Nessie resource for a ledger row, or None when it has no Nessie equivalent."""
    if t.account_type in LOAN_TYPES or t.flow_class == "non_cash":
        return None
    if t.flow_class == "internal_transfer":
        return "transfer"
    if t.flow_class in ("income", "external_transfer") and t.balance_change > 0:
        return "deposit"
    if t.merchant_key:
        return "purchase"
    if t.flow_class in ("expense", "external_transfer"):
        return "withdrawal"
    return None


def _skip_reason(t: Transaction) -> str:
    if t.account_type in LOAN_TYPES:
        return "loan-account row: Nessie loans have no transaction history (kept in Waypoint)"
    if t.flow_class == "non_cash":
        return "non-cash accrual: no Nessie equivalent (kept in Waypoint as PNC-only)"
    return "no Nessie equivalent"


def _transfer_direction(t: Transaction) -> str:
    if t.transaction_type == "transfer_in" or (t.transaction_type == "payment" and t.account_type == "credit_card"):
        return "in"
    return "out"


def _op(local_key, resource, body, parent=None, refs=None, mark=None, source_id=None, flow=None, sources=None):
    model = CREATE_MODELS[resource]
    model.model_validate(body)  # fail fast if the body would be rejected by Nessie
    return SeedOperation(local_key=local_key, resource=resource, parent_key=parent, body=body,
                         refs=refs or {}, marker=mark, source_record_id=source_id, source_flow_class=flow,
                         field_sources=sources or {})


def build_seed_plan(profile: StudentProfile, gen: GeneratedFields) -> SeedPlan:
    pid = profile.profile_id
    ops: list[SeedOperation] = []
    skipped: list[SkippedRecord] = []
    medium, status = gen.transaction_medium, gen.transaction_status
    c = gen.customer

    customer_key = f"{pid}:customer"
    ops.append(_op(customer_key, "customer", {
        "first_name": c.first_name, "last_name": c.last_name,
        "address": {"street_number": c.street_number, "street_name": c.street_name,
                    "city": c.city, "state": c.state, "zip": c.zip}},
        source_id=pid, sources={"first_name": Origin.WAYPOINT_GENERATED, "last_name": Origin.WAYPOINT_GENERATED,
                                "address": Origin.WAYPOINT_GENERATED}))

    for m in profile.merchants:
        ops.append(_op(merchant_local_key(m.merchant_key), "merchant", {
            "name": m.name, "category": m.category,
            "address": {"street_number": m.street_number, "street_name": m.street_name,
                        "city": m.city, "state": m.state, "zip": m.zip},
            "geocode": {"lat": m.lat, "lng": m.lng}},
            source_id=m.merchant_key,
            sources={"name": Origin.PNC_GENERATED, "category": Origin.PNC_GENERATED,
                     "address": Origin.WAYPOINT_GENERATED, "geocode": Origin.WAYPOINT_GENERATED}))

    expected = {}
    nessie_accounts = set()
    for a in profile.accounts:
        if a.account_type not in NESSIE_ACCOUNT_TYPES:
            continue
        key = account_key(pid, a.account_id)
        mark = marker(pid, a.account_type)
        ops.append(_op(key, "account", {
            "type": NESSIE_ACCOUNT_TYPES[a.account_type], "nickname": f"{a.name} {mark}",
            "rewards": gen.account_rewards.get(a.account_id, 0), "balance": a.balance},
            parent=customer_key, mark=mark, source_id=a.account_id,
            sources={"type": Origin.PNC_GENERATED, "nickname": Origin.PNC_GENERATED,
                     "balance": Origin.DERIVED, "rewards": Origin.DERIVED}))
        expected[key] = a.balance
        nessie_accounts.add(a.account_id)

    checking = profile.account_of_type("checking")
    loan_fields = {lf.account_id: lf for lf in gen.loans}
    for a in profile.accounts:
        if a.account_type not in LOAN_TYPES:
            continue
        lf = loan_fields[a.account_id]
        mark = marker(pid, a.account_type)
        ops.append(_op(f"{pid}:loan:{a.account_id}", "loan", {
            "type": lf.loan_type, "status": lf.status, "credit_score": lf.credit_score,
            "monthly_payment": a.monthly_payment, "amount": a.balance,
            "description": f"{a.name} {mark}"},
            parent=account_key(pid, checking.account_id), mark=mark, source_id=a.account_id,
            sources={"type": Origin.PNC_GENERATED, "status": Origin.PNC_GENERATED,
                     "credit_score": Origin.WAYPOINT_GENERATED, "monthly_payment": Origin.PNC_GENERATED,
                     "amount": Origin.DERIVED}))

    for b in profile.bills:
        mark = marker(b.bill_key)
        ops.append(_op(f"{pid}:bill:{b.bill_key}", "bill", {
            "status": gen.bill_status, "payee": b.payee, "nickname": f"{b.nickname} {mark}",
            "payment_date": next_occurrence(profile.as_of_date, b.day_of_month).isoformat(),
            "recurring_date": b.day_of_month, "payment_amount": b.amount},
            parent=account_key(pid, b.account_id), mark=mark, source_id=b.bill_key,
            sources={"payee": Origin.PNC_GENERATED, "payment_amount": Origin.PNC_GENERATED,
                     "recurring_date": Origin.PNC_GENERATED, "status": Origin.WAYPOINT_GENERATED,
                     "payment_date": Origin.DERIVED}))

    for t in profile.transactions:
        resource = classify_transaction(t)
        if resource is None or t.account_id not in nessie_accounts:
            skipped.append(SkippedRecord(record_id=t.transaction_id, reason=_skip_reason(t)))
            continue
        mark = marker(t.transaction_id)
        when = t.posted_date.isoformat()
        refs = {}
        if resource == "purchase":
            mref = merchant_local_key(t.merchant_key)
            refs["merchant_id"] = mref
            body = {"merchant_id": REF_PREFIX + mref, "medium": medium, "purchase_date": when,
                    "status": status, "amount": t.amount, "description": f"{t.description} {mark}"}
        elif resource == "transfer":
            body = {"transaction_date": when, "status": status, "amount": t.amount,
                    "description": f"{t.description} ({_transfer_direction(t)}) {mark}"}
        else:
            body = {"medium": medium, "transaction_date": when, "status": status, "amount": t.amount,
                    "description": f"{t.description} {mark}"}
        ops.append(_op(f"{pid}:txn:{t.transaction_id}", resource, body,
                       parent=account_key(pid, t.account_id), refs=refs, mark=mark,
                       source_id=t.transaction_id, flow=t.flow_class,
                       sources={"amount": Origin.PNC_GENERATED, "date": Origin.PNC_GENERATED,
                                "description": Origin.PNC_GENERATED, "medium": Origin.WAYPOINT_GENERATED,
                                "status": Origin.WAYPOINT_GENERATED}))

    counts: dict[str, int] = {}
    for op in ops:
        counts[op.resource] = counts.get(op.resource, 0) + 1
    counts["skipped"] = len(skipped)
    notes = ["Nessie transactions do not change balances; accounts are created with closing balances.",
             "Each internal transfer is recorded as one Transfer per Nessie account leg; pairing stays in Waypoint."]
    if any(op.resource == "loan" and op.body["monthly_payment"] == 0 for op in ops):
        notes.append("A deferred student loan has monthly_payment=0; confirm Nessie accepts 0 when seeding.")
    return SeedPlan(profile_id=pid, operations=ops, skipped=skipped, expected_account_balances=expected,
                    counts=counts, notes=notes)
