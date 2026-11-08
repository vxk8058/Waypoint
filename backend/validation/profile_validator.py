"""Financial-consistency validation for student profiles and their Nessie seed plans.

Errors make a profile unusable; warnings flag realism concerns. Every check is
deterministic and listed in `CHECKS` so reports show what was verified.
"""
from collections import Counter, defaultdict

from pydantic import BaseModel

from ..schemas.nessie import CREATE_MODELS, REF_PREFIX
from ..schemas.seed_plan import SeedPlan
from ..schemas.student import ASSET_TYPES, LIABILITY_TYPES, StudentProfile
from ..mapping.pnc_to_nessie import classify_transaction

INCOME_TOLERANCE = 0.10    # observed vs planned monthly income
SPENDING_TOLERANCE = 0.15  # observed vs planned monthly non-debt spending

CHECKS = [
    "whole_dollars", "unique_ids", "account_references", "ledger_reconciliation", "running_balances",
    "statement_reconciliation", "no_negative_assets", "credit_limit", "transfer_pairs",
    "flow_class_rules", "bill_payments", "merchant_references", "goal_consistency",
    "assumptions_vs_observed", "student_realism", "seed_plan_bodies", "seed_plan_references",
    "seed_plan_coverage", "seed_plan_balances",
]


class Issue(BaseModel):
    check: str
    message: str
    record_id: str | None = None


class ValidationReport(BaseModel):
    profile_id: str
    ok: bool
    errors: list[Issue]
    warnings: list[Issue]
    checks_run: list[str]
    stats: dict


def validate_profile(profile: StudentProfile, plan: SeedPlan | None = None) -> ValidationReport:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    err = lambda c, m, r=None: errors.append(Issue(check=c, message=m, record_id=r))  # noqa: E731
    warn = lambda c, m, r=None: warnings.append(Issue(check=c, message=m, record_id=r))  # noqa: E731
    accounts = {a.account_id: a for a in profile.accounts}
    txs = profile.transactions

    # whole_dollars: pydantic coerces 1.0 -> 1 but rejects 1.5 for int; double-check types.
    for t in txs:
        for field in ("amount", "balance_change", "balance_after"):
            if not isinstance(getattr(t, field), int):
                err("whole_dollars", f"{field} is not a whole-dollar int", t.transaction_id)
    for a in profile.accounts:
        if not isinstance(a.balance, int) or not isinstance(a.opening_balance, int):
            err("whole_dollars", "account balance is not a whole-dollar int", a.account_id)

    # unique_ids / account_references
    for label, ids in (("transaction", [t.transaction_id for t in txs]),
                       ("account", [a.account_id for a in profile.accounts]),
                       ("bill", [b.bill_key for b in profile.bills])):
        for dup, n in Counter(ids).items():
            if n > 1:
                err("unique_ids", f"duplicate {label} id ({n}x)", dup)
    for t in txs:
        a = accounts.get(t.account_id)
        if a is None:
            err("account_references", "transaction references unknown account", t.transaction_id)
        elif a.account_type != t.account_type:
            err("account_references", "transaction account_type mismatch", t.transaction_id)

    # ledger_reconciliation / running_balances / no_negative_assets / credit_limit
    by_account = defaultdict(list)
    for t in txs:
        by_account[t.account_id].append(t)
    for acct_id, a in accounts.items():
        rows = sorted(by_account[acct_id], key=lambda t: t.transaction_id)
        if a.opening_balance + sum(t.balance_change for t in rows) != a.balance:
            err("ledger_reconciliation", "opening + sum(balance_change) != closing balance", acct_id)
        running = a.opening_balance
        for t in rows:
            running += t.balance_change
            if running != t.balance_after:
                err("running_balances", f"balance_after {t.balance_after} != running {running}", t.transaction_id)
                break
            if running < 0:
                err("no_negative_assets", "balance goes negative", t.transaction_id)
                break
        if a.account_type == "credit_card" and a.credit_limit is not None:
            peak = max([a.opening_balance] + [t.balance_after for t in rows])
            if peak > a.credit_limit:
                err("credit_limit", f"card balance {peak} exceeds limit {a.credit_limit}", acct_id)
            elif a.credit_limit and peak / a.credit_limit > 0.9:
                warn("credit_limit", "card balance above 90% of limit", acct_id)
        if a.account_type in LIABILITY_TYPES:
            for t in rows:
                if t.flow_class == "income":
                    err("flow_class_rules", "income posted to a liability account", t.transaction_id)

    # statement_reconciliation
    stmts = defaultdict(list)
    for s in profile.statements:
        stmts[s.account_id].append(s)
        if s.opening_balance + s.balance_increases - s.balance_decreases != s.closing_balance:
            err("statement_reconciliation", f"statement {s.month} does not reconcile", s.account_id)
    for acct_id, rows in stmts.items():
        rows.sort(key=lambda s: s.month)
        for prev, cur in zip(rows, rows[1:]):
            if prev.closing_balance != cur.opening_balance:
                err("statement_reconciliation", f"{cur.month} opening != previous closing", acct_id)
        if rows and rows[-1].closing_balance != accounts[acct_id].balance:
            err("statement_reconciliation", "last statement closing != account balance", acct_id)
        if rows and rows[0].opening_balance != accounts[acct_id].opening_balance:
            err("statement_reconciliation", "first statement opening != account opening balance", acct_id)

    # transfer_pairs: exactly two legs, same date/amount, different accounts, money conserved.
    legs = defaultdict(list)
    for t in txs:
        if t.flow_class == "internal_transfer":
            if not t.transfer_id:
                err("transfer_pairs", "internal transfer without transfer_id", t.transaction_id)
            legs[t.transfer_id].append(t)
        elif t.transfer_id:
            err("transfer_pairs", "transfer_id on a non-transfer row", t.transaction_id)
    for tid, pair in legs.items():
        if len(pair) != 2:
            err("transfer_pairs", f"expected 2 legs, found {len(pair)}", tid)
            continue
        x, y = pair
        if x.posted_date != y.posted_date or x.amount != y.amount or x.account_id == y.account_id:
            err("transfer_pairs", "legs differ in date/amount or share an account", tid)
        # Economic value: assets count +change, liabilities count -change; must net to zero.
        value = sum(t.balance_change if t.account_type in ASSET_TYPES else -t.balance_change for t in pair)
        if value != 0:
            err("transfer_pairs", "transfer legs do not conserve money", tid)

    # flow_class_rules
    for t in txs:
        if t.flow_class == "income" and t.balance_change <= 0:
            err("flow_class_rules", "income row does not increase balance", t.transaction_id)
        if t.flow_class == "expense":
            expected_sign = 1 if t.account_type in LIABILITY_TYPES else -1
            if t.balance_change * expected_sign <= 0:
                err("flow_class_rules", "expense row has wrong balance direction", t.transaction_id)
        if t.account_type == "credit_card" and t.transaction_type == "payment" and t.flow_class != "internal_transfer":
            err("flow_class_rules", "card payment must be an internal transfer (avoids double counting)",
                t.transaction_id)
        if t.transaction_type == "interest_accrual" and t.flow_class != "non_cash":
            err("flow_class_rules", "interest accrual must be non_cash", t.transaction_id)

    # bill_payments: payments reference a bill, match its amount, one per month.
    bills = {b.bill_key: b for b in profile.bills}
    months = {s.month for s in profile.statements}
    paid = defaultdict(set)
    for t in txs:
        if t.bill_key:
            b = bills.get(t.bill_key)
            if b is None:
                err("bill_payments", "payment references unknown bill", t.transaction_id)
                continue
            if t.amount != b.amount or t.account_id != b.account_id or t.flow_class != "expense":
                err("bill_payments", "bill payment differs from bill amount/account", t.transaction_id)
            paid[t.bill_key].add(t.posted_date.strftime("%Y-%m"))
    for key in bills:
        missing = months - paid[key]
        if missing:
            warn("bill_payments", f"no payment in {sorted(missing)}", key)

    # merchant_references
    merchant_keys = {m.merchant_key for m in profile.merchants}
    for t in txs:
        if t.transaction_type == "purchase" and t.merchant_key not in merchant_keys:
            err("merchant_references", "purchase without a known merchant", t.transaction_id)

    # goal_consistency: earmark never exceeds linked savings; contributions reconcile.
    g = profile.goal
    linked = accounts.get(g.linked_account_id)
    if linked is None or linked.account_type != "savings":
        err("goal_consistency", "goal must link to a savings account", g.goal_id)
    else:
        if g.current_saved > linked.balance:
            err("goal_consistency", "goal current_saved exceeds linked savings balance", g.goal_id)
        if g.initial_saved > linked.opening_balance:
            err("goal_consistency", "goal initial_saved exceeds savings opening balance", g.goal_id)
        contributed = sum(t.amount for t in txs if t.account_id == linked.account_id
                          and t.category == "goal_contribution" and t.balance_change > 0)
        if g.initial_saved + contributed != g.current_saved:
            err("goal_consistency", "current_saved != initial_saved + goal contributions", g.goal_id)
    if g.current_saved >= g.target_amount:
        warn("goal_consistency", "goal already reached", g.goal_id)
    if g.target_date <= profile.as_of_date:
        err("goal_consistency", "goal target_date is not in the future", g.goal_id)

    # assumptions_vs_observed / student_realism
    n = max(len(months), 1)
    income = sum(t.amount for t in txs if t.flow_class == "income") / n
    spending = sum(t.amount for t in txs if t.flow_class == "expense") / n
    a = profile.assumptions
    if a.monthly_income and abs(income - a.monthly_income) / a.monthly_income > INCOME_TOLERANCE:
        err("assumptions_vs_observed", f"observed income {income:.0f} vs planned {a.monthly_income}")
    if a.monthly_non_debt_expenses and abs(spending - a.monthly_non_debt_expenses) / a.monthly_non_debt_expenses > SPENDING_TOLERANCE:
        err("assumptions_vs_observed", f"observed spending {spending:.0f} vs planned {a.monthly_non_debt_expenses}")
    card = profile.account_of_type("credit_card")
    if card and card.credit_limit != a.credit_limit:
        err("assumptions_vs_observed", "card limit differs from profile credit_limit", card.account_id)
    if not 300 <= income <= 4000:
        warn("student_realism", f"monthly income {income:.0f} outside typical student range 300-4000")
    if income and spending > income * 1.2:
        warn("student_realism", "spending exceeds income by more than 20%")

    # Seed-plan checks ---------------------------------------------------------
    if plan is not None:
        keys = [op.local_key for op in plan.operations]
        for dup, cnt in Counter(keys).items():
            if cnt > 1:
                err("seed_plan_references", f"duplicate local_key ({cnt}x)", dup)
        markers = [op.marker for op in plan.operations if op.marker]
        for dup, cnt in Counter(markers).items():
            if cnt > 1:
                err("seed_plan_references", f"duplicate marker ({cnt}x)", dup)
        known = set(keys)
        for op in plan.operations:
            try:
                CREATE_MODELS[op.resource].model_validate(op.body)
            except Exception as exc:  # noqa: BLE001 - report every invalid body
                err("seed_plan_bodies", f"{op.resource} body rejected: {exc}", op.local_key)
            if op.parent_key and op.parent_key not in known:
                err("seed_plan_references", "parent_key not created earlier in plan", op.local_key)
            for field, ref in op.refs.items():
                if ref not in known or op.body.get(field) != REF_PREFIX + ref:
                    err("seed_plan_references", f"unresolvable ref for {field}", op.local_key)
            if op.parent_key and keys.index(op.parent_key) > keys.index(op.local_key):
                err("seed_plan_references", "parent created after child", op.local_key)
        sent = {op.source_record_id for op in plan.operations if op.source_record_id}
        skipped = {s.record_id for s in plan.skipped}
        for t in txs:
            in_plan, is_skipped = t.transaction_id in sent, t.transaction_id in skipped
            if in_plan == is_skipped:
                err("seed_plan_coverage", "transaction must be either planned or skipped (exactly one)",
                    t.transaction_id)
            if in_plan and classify_transaction(t) is None:
                err("seed_plan_coverage", "non-mappable row was planned", t.transaction_id)
        for op in plan.operations:
            if op.resource == "account":
                acct = accounts[op.source_record_id]
                if op.body["balance"] != acct.balance:
                    err("seed_plan_balances", "Nessie account balance != closing balance", op.local_key)
            if op.resource == "loan" and op.body["amount"] != accounts[op.source_record_id].balance:
                err("seed_plan_balances", "Nessie loan amount != loan balance", op.local_key)

    stats = {
        "transactions": len(txs), "months": len(months),
        "observed_monthly_income": round(income), "observed_monthly_spending": round(spending),
        "internal_transfer_pairs": len(legs),
        "plan_operations": len(plan.operations) if plan else None,
        "plan_skipped": len(plan.skipped) if plan else None,
    }
    return ValidationReport(profile_id=profile.profile_id, ok=not errors, errors=errors, warnings=warnings,
                            checks_run=CHECKS if plan else [c for c in CHECKS if not c.startswith("seed_plan")],
                            stats=stats)
