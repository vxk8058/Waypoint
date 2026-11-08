"""Verify seeded data by reading it back from Nessie and comparing it with the plan and
the original PNC-convention ledger."""
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import BaseModel
from pymongo.database import Database

from ..integrations.nessie.client import NessieClient
from ..integrations.nessie.resources import ACCOUNT_CHILDREN, LIST_PATHS
from ..mapping.nessie_to_unified import nessie_balance_change
from ..schemas.seed_plan import SeedPlan
from ..schemas.student import StudentProfile
from .seeder import GLOBAL, find_marker, map_scope

# Fields compared between the plan body and the Nessie record (purchase_date etc. per resource).
COMPARE = {
    "customer": ("first_name", "last_name", "address"),
    "account": ("type", "nickname", "rewards", "balance"),
    "loan": ("type", "status", "credit_score", "monthly_payment", "amount", "description"),
    "bill": ("status", "payee", "nickname", "payment_date", "recurring_date", "payment_amount"),
    "deposit": ("medium", "transaction_date", "status", "amount", "description"),
    "withdrawal": ("medium", "transaction_date", "status", "amount", "description"),
    "purchase": ("merchant_id", "medium", "purchase_date", "status", "amount", "description"),
    "transfer": ("transaction_date", "status", "amount", "description"),
    "merchant": ("name", "category", "address"),
}


class AccountCheck(BaseModel):
    local_key: str
    nessie_id: str | None
    expected_balance: int
    nessie_balance: int | None
    ledger_net_activity: int
    nessie_net_activity: int | None
    ok: bool


class VerificationReport(BaseModel):
    profile_id: str
    ok: bool
    checked_at: datetime
    nessie_customer_id: str | None
    expected_counts: dict[str, int]
    found_counts: dict[str, int]
    accounts: list[AccountCheck]
    missing: list[dict]
    mismatches: list[dict]
    unexpected: list[dict]
    income_by_month: dict[str, dict]
    api_calls: int


def _norm_addr(v):
    return {k: str(v.get(k, "")) for k in ("street_number", "street_name", "city", "state", "zip")} if isinstance(v, dict) else v


def _signed(resource: str, account_type: str, record: dict) -> int:
    return nessie_balance_change(resource, account_type, int(record.get("amount", 0)), record.get("description"))


def verify_profile(profile: StudentProfile, plan: SeedPlan, client: NessieClient, db: Database) -> VerificationReport:
    pid = profile.profile_id
    calls_before = client.calls
    id_map = {(d["profile_id"], d["local_key"]): d["nessie_id"]
              for d in db.nessie_id_map.find({"profile_id": {"$in": [pid, GLOBAL]}})}
    missing, mismatches, unexpected = [], [], []
    expected_counts: dict[str, int] = defaultdict(int)
    found_counts: dict[str, int] = defaultdict(int)
    for op in plan.operations:
        expected_counts[op.resource] += 1

    def nid(op):
        return id_map.get((map_scope(pid, op), op.local_key))

    # Fetch customer, merchants and every account's children once.
    customer_op = next(op for op in plan.operations if op.resource == "customer")
    customer_id = nid(customer_op)
    records: dict[str, dict] = {}
    if customer_id:
        cust = client.get_or_none(f"/customers/{customer_id}")
        if cust:
            records[customer_id] = cust
    merchant_ids = {nid(op) for op in plan.operations if op.resource == "merchant"}
    for m in client.list(LIST_PATHS["merchant"]):
        if m["_id"] in merchant_ids:
            records[m["_id"]] = m
    accounts = client.list(LIST_PATHS["account"].format(parent=customer_id)) if customer_id else []
    children: dict[str, dict[str, list[dict]]] = {}
    for acct in accounts:
        records[acct["_id"]] = acct
        children[acct["_id"]] = {}
        for resource in ACCOUNT_CHILDREN:
            rows = client.list(LIST_PATHS[resource].format(parent=acct["_id"]))
            children[acct["_id"]][resource] = rows
            for r in rows:
                records[r["_id"]] = r

    # Every planned record exists and matches the plan body.
    planned_ids = set()
    for op in plan.operations:
        nessie_id = nid(op)
        if nessie_id is None or nessie_id not in records:
            missing.append({"local_key": op.local_key, "resource": op.resource, "nessie_id": nessie_id})
            continue
        planned_ids.add(nessie_id)
        found_counts[op.resource] += 1
        rec = records[nessie_id]
        for field_name in COMPARE[op.resource]:
            want = op.body.get(field_name)
            if field_name in op.refs:
                want = id_map.get((GLOBAL, op.refs[field_name]))
            have = rec.get(field_name)
            if field_name == "address":
                want, have = _norm_addr(want), _norm_addr(have)
            if want != have:
                mismatches.append({"local_key": op.local_key, "field": field_name, "expected": want, "nessie": have})

    # Marker-tagged records for this profile that the plan does not know about.
    prefix = f"[wp:{pid}"
    for acct_id, by_res in children.items():
        for resource, rows in by_res.items():
            for r in rows:
                if r["_id"] not in planned_ids and (find_marker(r, resource) or "").startswith(prefix):
                    unexpected.append({"resource": resource, "nessie_id": r["_id"], "marker": find_marker(r, resource)})
    for acct in accounts:
        if acct["_id"] not in planned_ids and (find_marker(acct, "account") or "").startswith(prefix):
            unexpected.append({"resource": "account", "nessie_id": acct["_id"], "marker": find_marker(acct, "account")})

    # Balance and activity reconciliation per account.
    ledger_net = defaultdict(int)
    planned_sources = {op.source_record_id for op in plan.operations}
    for t in profile.transactions:
        if t.transaction_id in planned_sources:
            ledger_net[t.account_id] += t.balance_change
    account_checks = []
    for op in plan.operations:
        if op.resource != "account":
            continue
        acct_id = nid(op)
        acct_type = profile.account(op.source_record_id).account_type
        rec = records.get(acct_id) if acct_id else None
        net = None
        if rec is not None:
            net = sum(_signed(res, acct_type, r) for res in ("deposit", "withdrawal", "purchase", "transfer")
                      for r in children.get(acct_id, {}).get(res, []) if r["_id"] in planned_ids)
        expected = plan.expected_account_balances[op.local_key]
        account_checks.append(AccountCheck(
            local_key=op.local_key, nessie_id=acct_id, expected_balance=expected,
            nessie_balance=rec.get("balance") if rec else None,
            ledger_net_activity=ledger_net[op.source_record_id], nessie_net_activity=net,
            ok=rec is not None and rec.get("balance") == expected and net == ledger_net[op.source_record_id]))

    # Income check: Nessie deposits per month vs PNC income rows.
    income = defaultdict(lambda: {"pnc": 0, "nessie": 0})
    for t in profile.transactions:
        if t.flow_class == "income":
            income[t.posted_date.strftime("%Y-%m")]["pnc"] += t.amount
    for acct_id, by_res in children.items():
        for r in by_res.get("deposit", []):
            if r["_id"] in planned_ids:
                income[r["transaction_date"][:7]]["nessie"] += int(r["amount"])
    income_ok = all(v["pnc"] == v["nessie"] for v in income.values())

    ok = (not missing and not mismatches and not unexpected and income_ok and all(a.ok for a in account_checks)
          and dict(found_counts) == dict(expected_counts))
    return VerificationReport(
        profile_id=pid, ok=ok, checked_at=datetime.now(timezone.utc), nessie_customer_id=customer_id,
        expected_counts=dict(expected_counts), found_counts=dict(found_counts), accounts=account_checks,
        missing=missing, mismatches=mismatches, unexpected=unexpected, income_by_month=dict(sorted(income.items())),
        api_calls=client.calls - calls_before)
