"""Build the unified Waypoint profile, and source-agnostic aggregates over it.

`summarize`, `wellness_inputs` and `pnc_view` work on unified accounts/transactions, so the
same numbers come out whether the profile was built from the PNC-convention profile
(pre_seed, Phase 2) or from Nessie responses (Phase 4).

Monthly summary rules follow PNC `Lab_Package/financial_tools.summarize_transaction_history`:
- income   = rows with flow_class "income"
- spending = rows with flow_class "expense" (card purchases counted once; card payments,
             loan payments and internal transfers are never spending; bill payments are
             counted once via their payment row, never via the bill schedule)
- debt_payments = liability-side payment rows only (not the checking counterpart)
- interest and fees reported separately; asset interest is non-cash
"""
from collections import Counter, defaultdict
from datetime import date

from ..schemas.common import Origin, SourceMeta
from ..schemas.normalized import (
    MonthlySummary, UnifiedAccount, UnifiedBill, UnifiedGoal, UnifiedProfile, UnifiedTransaction,
    UnifiedUser, WellnessInputs,
)
from ..schemas.seed_plan import SeedPlan
from ..schemas.student import ASSET_TYPES, LIABILITY_TYPES, StudentProfile
from .missing_fields import GeneratedFields
from .pnc_to_nessie import account_key, classify_transaction, next_occurrence

PNC = Origin.PNC_GENERATED


def months_between(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def direction_of(account_type: str, balance_change: int) -> str:
    """Money into the account: assets increase, liabilities decrease."""
    if account_type in LIABILITY_TYPES:
        return "in" if balance_change < 0 else "out"
    return "in" if balance_change > 0 else "out"


def summarize(transactions: list[UnifiedTransaction], accounts: list[UnifiedAccount],
              history_start: date, as_of: date) -> list[MonthlySummary]:
    rows = defaultdict(Counter)
    for t in transactions:
        r = rows[t.date.strftime("%Y-%m")]
        if t.flow_class == "income":
            r["income"] += t.amount
        if t.flow_class == "expense":
            r["spending"] += t.amount
        if t.account_type in LIABILITY_TYPES and t.type == "payment":
            r["debt_payments"] += t.amount
        if t.type == "interest_accrual":
            r["asset_interest" if t.account_type in ASSET_TYPES else "debt_interest"] += t.amount
        if t.type == "fee":
            r["fees"] += t.amount
        if t.account_type == "savings" and t.type == "transfer_in":
            r["savings_contributions"] += t.amount
            if t.category == "goal_contribution":
                r["goal_contributions"] += t.amount
        if t.account_type in ASSET_TYPES and t.flow_class != "non_cash":
            r["net_cash_flow"] += t.balance_change

    # Month-end balances, rebuilt backwards from current balances (Nessie has no statements).
    after = defaultdict(Counter)  # month -> account_id -> change posted after that month
    months = months_between(history_start, as_of)
    for t in transactions:
        ym = t.date.strftime("%Y-%m")
        for m in months:
            if ym > m:
                after[m][t.account_id] += t.balance_change
    out = []
    for m in months:
        r = rows[m]
        liquid = sum(a.balance - after[m][a.account_id] for a in accounts if a.type in ASSET_TYPES)
        debts = sum(a.balance - after[m][a.account_id] for a in accounts if a.type in LIABILITY_TYPES)
        out.append(MonthlySummary(
            month=m, income=r["income"], spending=r["spending"], debt_payments=r["debt_payments"],
            debt_interest=r["debt_interest"], asset_interest=r["asset_interest"], fees=r["fees"],
            savings_contributions=r["savings_contributions"], goal_contributions=r["goal_contributions"],
            net_cash_flow=r["net_cash_flow"], closing_liquid=liquid, closing_assets=liquid, closing_debts=debts))
    return out


def wellness_inputs(accounts: list[UnifiedAccount], bills: list[UnifiedBill], summary: list[MonthlySummary],
                    goal: UnifiedGoal) -> WellnessInputs:
    n = max(len(summary), 1)
    assets = sum(a.balance for a in accounts if a.type in ASSET_TYPES)
    debts = sum(a.balance for a in accounts if a.type in LIABILITY_TYPES)
    cards = [a for a in accounts if a.type == "credit_card"]
    return WellnessInputs(
        history_months=len(summary),
        monthly_income_avg=round(sum(m.income for m in summary) / n),
        monthly_spending_avg=round(sum(m.spending for m in summary) / n),
        monthly_recurring_bills=sum(b.amount for b in bills if b.status in ("recurring", "pending")),
        scheduled_monthly_debt_payments=sum(a.monthly_payment for a in accounts if a.type in LIABILITY_TYPES),
        monthly_goal_contribution=goal.monthly_contribution,
        liquid_cash=assets, total_assets=assets, total_liabilities=debts, net_worth=assets - debts,
        credit_card_balance=sum(a.balance for a in cards),
        credit_limit_total=sum(a.credit_limit or 0 for a in cards))


def pnc_view(profile_id: str, accounts: list[UnifiedAccount], inputs: WellnessInputs) -> dict:
    """Shape accepted by the vendored PNC `wellness.metrics.compute_metrics`."""
    by_type: dict[str, int] = {}
    for a in accounts:
        by_type[a.type] = by_type.get(a.type, 0) + a.balance
    return {
        "customer_id": profile_id,
        "monthly_income": inputs.monthly_income_avg,
        "total_assets": inputs.total_assets,
        "total_liabilities": inputs.total_liabilities,
        "net_worth": inputs.net_worth,
        "liquid_cash": inputs.liquid_cash,
        "balances_by_type": by_type,
        "avg_monthly_spending": inputs.monthly_spending_avg,
        "monthly_debt_payments": inputs.scheduled_monthly_debt_payments,
        "accounts": [{"id": a.account_id, "type": a.type, "name": a.name, "balance": a.balance,
                      **({"credit_limit": a.credit_limit} if a.credit_limit is not None else {}),
                      "monthly_payment": a.monthly_payment} for a in accounts],
    }


def unified_goal(profile: StudentProfile, transactions=None) -> UnifiedGoal:
    g = profile.goal.model_dump()
    if transactions is not None:  # live: count goal deposits actually recorded, so new ones move the goal
        g["current_saved"] = g["initial_saved"] + sum(
            t.amount for t in transactions
            if t.category == "goal_contribution" and t.direction == "in" and t.account_id == g["linked_account_id"])
    return UnifiedGoal(**g, source=SourceMeta(origin=PNC, source_id=g["goal_id"],
                                              note="current_saved is derived from goal transfers"))


def unified_user(profile: StudentProfile, gen: GeneratedFields, nessie_customer_id: str | None = None,
                 name_override: tuple[str, str] | None = None) -> UnifiedUser:
    c = gen.customer
    first, last = name_override or (c.first_name, c.last_name)
    sources = {"first_name": gen.field_sources["customer.first_name"],
               "last_name": gen.field_sources["customer.last_name"],
               "address": gen.field_sources["customer.address"], "student": PNC}
    if name_override:
        sources.update(first_name=Origin.NESSIE, last_name=Origin.NESSIE, address=Origin.NESSIE)
    return UnifiedUser(
        profile_id=profile.profile_id, nessie_customer_id=nessie_customer_id, first_name=first, last_name=last,
        address={"street_number": c.street_number, "street_name": c.street_name, "city": c.city,
                 "state": c.state, "zip": c.zip},
        student=profile.student, sources=sources)


def pnc_account(a, nessie_local_key: str, nessie_resource: str, **overrides) -> UnifiedAccount:
    fields = dict(
        account_id=a.account_id, type=a.account_type, name=a.name, is_liability=a.account_type in LIABILITY_TYPES,
        balance=a.balance, opening_balance=a.opening_balance, credit_limit=a.credit_limit, apr_pct=a.apr_pct,
        apy_pct=a.annual_yield_pct, monthly_payment=a.monthly_payment, loan_status=a.loan_status,
        subsidized=a.subsidized, repayment_monthly_payment_estimate=a.repayment_monthly_payment_estimate,
        nessie_resource=nessie_resource, nessie_local_key=nessie_local_key,
        source=SourceMeta(origin=PNC, source_id=a.account_id))
    fields.update(overrides)
    return UnifiedAccount(**fields)


def assemble(profile: StudentProfile, data_mode: str, user: UnifiedUser, accounts, transactions, bills,
             metadata: dict) -> UnifiedProfile:
    goal = unified_goal(profile, transactions)
    summary = summarize(transactions, accounts, profile.history_start, profile.as_of_date)
    inputs = wellness_inputs(accounts, bills, summary, goal)
    return UnifiedProfile(
        profile_id=profile.profile_id, data_mode=data_mode, history_start=profile.history_start,
        as_of_date=profile.as_of_date, user=user, accounts=accounts, transactions=transactions, bills=bills,
        goal=goal, monthly_summary=summary, wellness_inputs=inputs,
        pnc_view=pnc_view(profile.profile_id, accounts, inputs), metadata=metadata)


def build_unified_profile(profile: StudentProfile, gen: GeneratedFields, plan: SeedPlan) -> UnifiedProfile:
    """Pre-seed unified profile, built from the PNC-convention profile (no Nessie calls)."""
    pid = profile.profile_id
    op_by_source = {op.source_record_id: op for op in plan.operations if op.source_record_id}
    merchants = {m.merchant_key: m.name for m in profile.merchants}

    accounts = []
    for a in profile.accounts:
        op = op_by_source[a.account_id]
        accounts.append(pnc_account(a, op.local_key, "loan" if op.resource == "loan" else "account"))

    transactions = []
    for t in profile.transactions:
        op = op_by_source.get(t.transaction_id)
        transactions.append(UnifiedTransaction(
            transaction_id=t.transaction_id, account_id=t.account_id, account_type=t.account_type,
            date=t.posted_date, type=t.transaction_type, category=t.category, description=t.description,
            amount=t.amount, direction=direction_of(t.account_type, t.balance_change),
            balance_change=t.balance_change, flow_class=t.flow_class,
            transfer_id=t.transfer_id, merchant_key=t.merchant_key, merchant_name=merchants.get(t.merchant_key),
            bill_key=t.bill_key, nessie_resource=classify_transaction(t) if op else None,
            nessie_local_key=op.local_key if op else None,
            source=SourceMeta(origin=PNC, source_id=t.transaction_id,
                              note=None if op else "PNC-only: not represented in Nessie")))

    bills = [UnifiedBill(
        bill_key=b.bill_key, payee=b.payee, nickname=b.nickname, category=b.category, amount=b.amount,
        day_of_month=b.day_of_month, next_due_date=next_occurrence(profile.as_of_date, b.day_of_month),
        account_id=b.account_id, status=gen.bill_status, nessie_local_key=op_by_source[b.bill_key].local_key,
        source=SourceMeta(origin=PNC, source_id=b.bill_key)) for b in profile.bills]

    origin_counts = Counter(t.source.note is None for t in transactions)
    return assemble(profile, "pre_seed", unified_user(profile, gen), accounts, transactions, bills, metadata={
        "generator": profile.generator, "seed": profile.seed, "persona_key": profile.persona_key,
        "is_primary_demo": profile.is_primary_demo,
        "transactions_in_nessie": origin_counts[True], "transactions_pnc_only": origin_counts[False],
        "seed_plan_counts": plan.counts, "account_key_format": account_key(pid, "<account_id>")})
