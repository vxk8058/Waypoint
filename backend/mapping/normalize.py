"""Build the unified Waypoint profile from a PNC-convention student profile.

Monthly summary rules follow PNC `Lab_Package/financial_tools.summarize_transaction_history`:
- income   = rows with flow_class "income"
- spending = rows with flow_class "expense" (card purchases counted once; card payments,
             loan payments and internal transfers are never spending; bill payments are
             counted once via their payment row, never via the bill schedule)
- debt_payments = liability-side payment rows only (not the checking counterpart)
- interest and fees reported separately; asset interest is non-cash
"""
from collections import Counter, defaultdict

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


def monthly_summary(profile: StudentProfile) -> list[MonthlySummary]:
    rows = defaultdict(lambda: Counter())
    for t in profile.transactions:
        r = rows[t.posted_date.strftime("%Y-%m")]
        if t.flow_class == "income":
            r["income"] += t.amount
        if t.flow_class == "expense":
            r["spending"] += t.amount
        if t.account_type in LIABILITY_TYPES and t.transaction_type == "payment":
            r["debt_payments"] += t.amount
        if t.transaction_type == "interest_accrual":
            r["asset_interest" if t.account_type in ASSET_TYPES else "debt_interest"] += t.amount
        if t.transaction_type == "fee":
            r["fees"] += t.amount
        if t.account_type == "savings" and t.transaction_type == "transfer_in":
            r["savings_contributions"] += t.amount
            if t.category == "goal_contribution":
                r["goal_contributions"] += t.amount
        if t.account_type in ASSET_TYPES and t.flow_class != "non_cash":
            r["net_cash_flow"] += t.balance_change
    closing = defaultdict(lambda: Counter())
    for s in profile.statements:
        c = closing[s.month]
        if s.account_type in ASSET_TYPES:
            c["assets"] += s.closing_balance
            c["liquid"] += s.closing_balance
        else:
            c["debts"] += s.closing_balance
    out = []
    for month in sorted({s.month for s in profile.statements}):
        r, c = rows[month], closing[month]
        out.append(MonthlySummary(
            month=month, income=r["income"], spending=r["spending"], debt_payments=r["debt_payments"],
            debt_interest=r["debt_interest"], asset_interest=r["asset_interest"], fees=r["fees"],
            savings_contributions=r["savings_contributions"], goal_contributions=r["goal_contributions"],
            net_cash_flow=r["net_cash_flow"], closing_liquid=c["liquid"], closing_assets=c["assets"],
            closing_debts=c["debts"]))
    return out


def pnc_view(profile: StudentProfile, inputs: WellnessInputs) -> dict:
    """Shape accepted by the vendored PNC `wellness.metrics.compute_metrics`."""
    by_type: dict[str, int] = {}
    for a in profile.accounts:
        by_type[a.account_type] = by_type.get(a.account_type, 0) + a.balance
    return {
        "customer_id": profile.profile_id,
        "monthly_income": inputs.monthly_income_avg,
        "total_assets": inputs.total_assets,
        "total_liabilities": inputs.total_liabilities,
        "net_worth": inputs.net_worth,
        "liquid_cash": inputs.liquid_cash,
        "balances_by_type": by_type,
        "avg_monthly_spending": inputs.monthly_spending_avg,
        "monthly_debt_payments": inputs.scheduled_monthly_debt_payments,
        "accounts": [{"id": a.account_id, "type": a.account_type, "name": a.name, "balance": a.balance,
                      **({"credit_limit": a.credit_limit} if a.credit_limit is not None else {}),
                      "monthly_payment": a.monthly_payment} for a in profile.accounts],
    }


def build_unified_profile(profile: StudentProfile, gen: GeneratedFields, plan: SeedPlan) -> UnifiedProfile:
    pid = profile.profile_id
    op_by_source = {op.source_record_id: op for op in plan.operations if op.source_record_id}
    merchants = {m.merchant_key: m.name for m in profile.merchants}
    c = gen.customer

    user = UnifiedUser(
        profile_id=pid, nessie_customer_id=None, first_name=c.first_name, last_name=c.last_name,
        address={"street_number": c.street_number, "street_name": c.street_name, "city": c.city,
                 "state": c.state, "zip": c.zip},
        student=profile.student,
        sources={"first_name": Origin.WAYPOINT_GENERATED, "last_name": Origin.WAYPOINT_GENERATED,
                 "address": Origin.WAYPOINT_GENERATED, "student": PNC})

    accounts = []
    for a in profile.accounts:
        op = op_by_source[a.account_id]
        accounts.append(UnifiedAccount(
            account_id=a.account_id, type=a.account_type, name=a.name, is_liability=a.account_type in LIABILITY_TYPES,
            balance=a.balance, opening_balance=a.opening_balance, credit_limit=a.credit_limit, apr_pct=a.apr_pct,
            apy_pct=a.annual_yield_pct, monthly_payment=a.monthly_payment, loan_status=a.loan_status,
            subsidized=a.subsidized, repayment_monthly_payment_estimate=a.repayment_monthly_payment_estimate,
            nessie_resource="loan" if op.resource == "loan" else "account", nessie_local_key=op.local_key,
            source=SourceMeta(origin=PNC, source_id=a.account_id)))

    transactions = []
    for t in profile.transactions:
        op = op_by_source.get(t.transaction_id)
        direction = "in" if t.balance_change > 0 else "out"
        if t.account_type in LIABILITY_TYPES:  # liability decreases are money "in" to that account
            direction = "in" if t.balance_change < 0 else "out"
        transactions.append(UnifiedTransaction(
            transaction_id=t.transaction_id, account_id=t.account_id, account_type=t.account_type,
            date=t.posted_date, type=t.transaction_type, category=t.category, description=t.description,
            amount=t.amount, direction=direction, balance_change=t.balance_change, flow_class=t.flow_class,
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

    g = profile.goal
    goal = UnifiedGoal(**g.model_dump(), source=SourceMeta(origin=PNC, source_id=g.goal_id,
                                                           note="current_saved is derived from goal transfers"))

    summary = monthly_summary(profile)
    n = len(summary)
    assets = sum(a.balance for a in profile.accounts if a.account_type in ASSET_TYPES)
    debts = sum(a.balance for a in profile.accounts if a.account_type in LIABILITY_TYPES)
    card = [a for a in profile.accounts if a.account_type == "credit_card"]
    inputs = WellnessInputs(
        history_months=n,
        monthly_income_avg=round(sum(m.income for m in summary) / n),
        monthly_spending_avg=round(sum(m.spending for m in summary) / n),
        monthly_recurring_bills=sum(b.amount for b in profile.bills),
        scheduled_monthly_debt_payments=sum(a.monthly_payment for a in profile.accounts
                                            if a.account_type in LIABILITY_TYPES),
        monthly_goal_contribution=g.monthly_contribution,
        liquid_cash=assets, total_assets=assets, total_liabilities=debts, net_worth=assets - debts,
        credit_card_balance=sum(a.balance for a in card),
        credit_limit_total=sum(a.credit_limit or 0 for a in card))

    origin_counts = Counter(t.source.note is None for t in transactions)
    return UnifiedProfile(
        profile_id=pid, data_mode="pre_seed", history_start=profile.history_start, as_of_date=profile.as_of_date,
        user=user, accounts=accounts, transactions=transactions, bills=bills, goal=goal,
        monthly_summary=summary, wellness_inputs=inputs, pnc_view=pnc_view(profile, inputs),
        metadata={"generator": profile.generator, "seed": profile.seed, "persona_key": profile.persona_key,
                  "is_primary_demo": profile.is_primary_demo,
                  "transactions_in_nessie": origin_counts[True], "transactions_pnc_only": origin_counts[False],
                  "seed_plan_counts": plan.counts,
                  "account_key_format": account_key(pid, "<account_id>")})
