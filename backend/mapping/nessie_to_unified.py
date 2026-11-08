"""Build the unified Waypoint profile from a Nessie snapshot plus PNC-only data.

- Banking data (balances, deposits, withdrawals, purchases, transfers, bills, loans,
  merchants) comes from Nessie: origin "nessie".
- The id map (nessie_id_map) links each Nessie record back to its PNC-convention row, which
  restores PNC-only meaning: category, flow_class, transfer pairing, bill link, APR, limits.
- Rows Nessie cannot hold (interest accruals, loan-account history) are added from the
  stored PNC profile: origin "pnc_generated".
- Nessie records Waypoint did not create (no mapping) are still included, with
  classification inferred from the Nessie resource type and noted as such.
"""
import re
from datetime import date

from ..integrations.nessie.gateway import NessieSnapshot
from ..schemas.common import Origin, SourceMeta
from ..schemas.normalized import UnifiedAccount, UnifiedBill, UnifiedProfile, UnifiedTransaction, UnifiedUser
from ..schemas.student import LIABILITY_TYPES, StudentProfile
from .missing_fields import GeneratedFields
from .normalize import assemble, direction_of, pnc_account
from .pnc_to_nessie import classify_transaction

NESSIE = Origin.NESSIE
NESSIE_ACCOUNT_TYPES = {"Checking": "checking", "Savings": "savings", "Credit Card": "credit_card"}
_MARKER = re.compile(r"\s*\[wp:[^\]]+\]")
_DIRECTION = re.compile(r"\s*\((in|out)\)\s*$")


def clean(text: str | None) -> str:
    """Strip Waypoint markers and transfer direction tags from Nessie text."""
    return _DIRECTION.sub("", _MARKER.sub("", text or "")).strip()


def transfer_incoming(description: str | None) -> bool:
    m = _DIRECTION.search(_MARKER.sub("", description or ""))
    return bool(m and m.group(1) == "in")


def nessie_balance_change(resource: str, account_type: str, amount: int, description: str | None = None) -> int:
    """Signed effect of a Nessie record on its account balance (PNC balance_change convention)."""
    liability = account_type in LIABILITY_TYPES
    if resource == "deposit":
        return -amount if liability else amount
    if resource == "withdrawal":
        return amount if liability else -amount
    if resource == "purchase":
        return amount if liability else -amount
    if resource == "transfer":
        incoming = transfer_incoming(description)
        if liability:
            return -amount if incoming else amount
        return amount if incoming else -amount
    return 0


def _record_date(resource: str, rec) -> date:
    return date.fromisoformat((rec.purchase_date if resource == "purchase" else rec.transaction_date)[:10])


def build_unified_from_nessie(profile: StudentProfile, gen: GeneratedFields, id_map: list[dict],
                              snap: NessieSnapshot) -> UnifiedProfile:
    by_nessie = {d["nessie_id"]: d for d in id_map}
    pnc_accounts = {a.account_id: a for a in profile.accounts}
    account_order = {a.account_id: i for i, a in enumerate(profile.accounts)}
    pnc_tx = {t.transaction_id: t for t in profile.transactions}
    pnc_bills = {b.bill_key: b for b in profile.bills}
    merchant_keys = {d["nessie_id"]: d["local_key"].split(":", 1)[1] for d in id_map if d["resource"] == "merchant"}
    warnings = list(snap.warnings)

    # Accounts (Nessie balance + PNC-only terms) -----------------------------
    accounts: list[UnifiedAccount] = []
    wid_for: dict[str, str] = {}  # Nessie account id -> Waypoint account id
    type_for: dict[str, str] = {}
    for na in snap.accounts:
        m = by_nessie.get(na.id)
        src = pnc_accounts.get(m["source_record_id"]) if m else None
        if src:
            acct = pnc_account(src, m["local_key"], "account", balance=int(na.balance), name=clean(na.nickname),
                               nessie_id=na.id, source=SourceMeta(origin=NESSIE, source_id=na.id))
        else:
            kind = NESSIE_ACCOUNT_TYPES.get(na.type, "checking")
            acct = UnifiedAccount(
                account_id=f"nessie-{na.id}", type=kind, name=clean(na.nickname) or na.type,
                is_liability=kind in LIABILITY_TYPES, balance=int(na.balance), opening_balance=int(na.balance),
                nessie_resource="account", nessie_local_key=f"nessie:{na.id}", nessie_id=na.id,
                source=SourceMeta(origin=NESSIE, source_id=na.id, note="not created by Waypoint; no PNC-only fields"))
            warnings.append(f"account {na.id} is not in the id map; included without PNC-only fields")
        accounts.append(acct)
        wid_for[na.id], type_for[na.id] = acct.account_id, acct.type

    for activity in snap.activity.values():
        for loan in activity.loan:
            m = by_nessie.get(loan.id)
            src = pnc_accounts.get(m["source_record_id"]) if m else None
            if src:
                accounts.append(pnc_account(
                    src, m["local_key"], "loan", balance=int(loan.amount), monthly_payment=int(loan.monthly_payment),
                    loan_status=loan.status or src.loan_status, nessie_id=loan.id,
                    source=SourceMeta(origin=NESSIE, source_id=loan.id)))
            else:
                kind = {"student": "student_loan", "auto": "auto_loan"}.get(loan.type, "loan")
                accounts.append(UnifiedAccount(
                    account_id=f"nessie-{loan.id}", type=kind, name=clean(loan.description) or f"{loan.type} loan",
                    is_liability=True, balance=int(loan.amount), opening_balance=int(loan.amount),
                    monthly_payment=int(loan.monthly_payment), loan_status=loan.status, nessie_resource="loan",
                    nessie_local_key=f"nessie:{loan.id}", nessie_id=loan.id,
                    source=SourceMeta(origin=NESSIE, source_id=loan.id, note="not created by Waypoint")))
                warnings.append(f"loan {loan.id} is not in the id map; included without PNC-only fields")
    accounts.sort(key=lambda a: account_order.get(a.account_id, len(account_order)))

    # Transactions from Nessie --------------------------------------------------
    transactions: list[UnifiedTransaction] = []
    seen: set[str] = set()
    for nessie_acct, activity in snap.activity.items():
        wid, kind = wid_for[nessie_acct], type_for[nessie_acct]
        for resource in ("deposit", "withdrawal", "purchase", "transfer"):
            for rec in getattr(activity, resource):
                amount = int(rec.amount)
                change = nessie_balance_change(resource, kind, amount, rec.description)
                merchant_id = getattr(rec, "merchant_id", None)
                merchant = snap.merchants.get(merchant_id) if merchant_id else None
                m = by_nessie.get(rec.id)
                src = pnc_tx.get(m["source_record_id"]) if m else None
                common = dict(account_id=wid, account_type=kind, date=_record_date(resource, rec),
                              description=clean(rec.description), amount=amount,
                              direction=direction_of(kind, change), balance_change=change,
                              merchant_name=merchant.name if merchant else None, nessie_resource=resource,
                              nessie_id=rec.id, source=SourceMeta(origin=NESSIE, source_id=rec.id))
                if src:
                    if src.balance_change != change:
                        warnings.append(f"{src.transaction_id}: Nessie amount/direction differs from ledger")
                    seen.add(src.transaction_id)
                    transactions.append(UnifiedTransaction(
                        transaction_id=src.transaction_id, type=src.transaction_type, category=src.category,
                        flow_class=src.flow_class, transfer_id=src.transfer_id,
                        merchant_key=merchant_keys.get(merchant_id, src.merchant_key), bill_key=src.bill_key,
                        nessie_local_key=m["local_key"], **common))
                else:
                    category = {"deposit": "deposit", "withdrawal": "other",
                                "transfer": "transfer"}.get(resource, None)
                    if resource == "purchase":
                        cat = merchant.category if merchant else None
                        category = (cat[0] if isinstance(cat, list) and cat else cat) or "other"
                    flow = {"deposit": "income", "transfer": "internal_transfer"}.get(resource, "expense")
                    ttype = {"deposit": "deposit", "withdrawal": "withdrawal", "purchase": "purchase",
                             "transfer": "transfer_in" if change > 0 or (kind in LIABILITY_TYPES and change < 0)
                             else "transfer_out"}[resource]
                    common["source"] = SourceMeta(origin=NESSIE, source_id=rec.id,
                                                  note="not created by Waypoint; classification inferred")
                    transactions.append(UnifiedTransaction(
                        transaction_id=f"nessie-{rec.id}", type=ttype, category=category, flow_class=flow,
                        merchant_key=merchant_keys.get(merchant_id), nessie_local_key=None, **common))

    # PNC-only rows (interest accruals, loan history) and missing Nessie rows -----------
    for t in profile.transactions:
        if t.transaction_id in seen:
            continue
        if classify_transaction(t) is not None and t.account_id in {a.account_id for a in accounts
                                                                     if a.nessie_resource == "account"}:
            warnings.append(f"{t.transaction_id} should be in Nessie but was not returned; omitted")
            continue
        transactions.append(UnifiedTransaction(
            transaction_id=t.transaction_id, account_id=t.account_id, account_type=t.account_type, date=t.posted_date,
            type=t.transaction_type, category=t.category, description=t.description, amount=t.amount,
            direction=direction_of(t.account_type, t.balance_change), balance_change=t.balance_change,
            flow_class=t.flow_class, transfer_id=t.transfer_id, merchant_key=t.merchant_key, bill_key=t.bill_key,
            nessie_resource=None, nessie_local_key=None,
            source=SourceMeta(origin=Origin.PNC_GENERATED, source_id=t.transaction_id,
                              note="PNC-only: not represented in Nessie")))
    transactions.sort(key=lambda t: (t.date, t.transaction_id))

    # Opening balances: derived from the current balance and the history.
    net = {}
    for t in transactions:
        net[t.account_id] = net.get(t.account_id, 0) + t.balance_change
    accounts = [a.model_copy(update={"opening_balance": a.balance - net.get(a.account_id, 0)}) for a in accounts]

    # Bills ---------------------------------------------------------------------
    bills = []
    for nessie_acct, activity in snap.activity.items():
        for rec in activity.bill:
            m = by_nessie.get(rec.id)
            src = pnc_bills.get(m["source_record_id"]) if m else None
            due = rec.upcoming_payment_date or rec.payment_date
            bills.append(UnifiedBill(
                bill_key=src.bill_key if src else f"nessie-{rec.id}", payee=rec.payee, nickname=clean(rec.nickname),
                category=src.category if src else "other", amount=int(rec.payment_amount),
                day_of_month=rec.recurring_date or (src.day_of_month if src else 1),
                next_due_date=date.fromisoformat(due[:10]) if due else profile.as_of_date,
                account_id=wid_for[nessie_acct], status=rec.status,
                nessie_local_key=m["local_key"] if m else f"nessie:{rec.id}", nessie_id=rec.id,
                source=SourceMeta(origin=NESSIE, source_id=rec.id,
                                  note=None if src else "not created by Waypoint")))
    bills.sort(key=lambda b: (b.next_due_date, b.bill_key))

    c = snap.customer
    user = UnifiedUser(
        profile_id=profile.profile_id, nessie_customer_id=c.id, first_name=c.first_name, last_name=c.last_name,
        address={k: str(c.address.get(k, "")) for k in ("street_number", "street_name", "city", "state", "zip")},
        student=profile.student,
        sources={"first_name": NESSIE, "last_name": NESSIE, "address": NESSIE, "student": Origin.PNC_GENERATED})

    origins: dict[str, int] = {}
    for t in transactions:
        origins[t.source.origin.value] = origins.get(t.source.origin.value, 0) + 1
    return assemble(profile, "nessie", user, accounts, transactions, bills, metadata={
        "persona_key": profile.persona_key, "is_primary_demo": profile.is_primary_demo,
        "nessie_customer_id": c.id, "fetched_at": snap.fetched_at.isoformat(), "nessie_api_calls": snap.api_calls,
        "transactions_by_origin": origins, "stale": False, "warnings": warnings})
