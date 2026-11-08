"""Deterministic synthetic student generator built on PNC conventions.

Reuses from the PNC toolkit / Lab_Package:
- `wellness.data_gen._amortized_payment` for loan payments.
- Ledger conventions from Lab_Package/generate_history.py: positive balances for assets
  and liabilities, `balance_change` sign per account, `flow_class`, paired internal
  transfers sharing a `transfer_id`, monthly-rate interest with half-up rounding, and
  reconciled monthly statements.

Differences from PNC (student-specific): whole-dollar amounts (Nessie truncates cents),
merchants on purchases, recurring bills, student loans, one goal, and forward simulation
from opening balances (PNC back-solves from snapshot balances; here both are generated,
so forward simulation keeps the ledger exact by construction).
"""
import calendar
import random
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import backend  # noqa: F401  (puts vendored PNC `wellness` on sys.path)
from wellness.data_gen import _amortized_payment

from ..schemas.common import Origin
from ..schemas.student import (
    LIABILITY_TYPES, Account, Assumptions, Employment, Goal, IncomeStream, Merchant,
    MonthlyStatement, RecurringBill, StudentInfo, StudentProfile, Transaction,
)
from .catalog import CITIES, MERCHANTS, merchant_key
from .personas import PERSONAS, Persona

GENERATOR = "waypoint-student-gen/1 (PNC wellness conventions @55999ab)"
DEFAULT_AS_OF = date(2026, 10, 31)
DEFAULT_MONTHS = 6
CHECKING_FLOOR = 50
SUMMER_MONTHS = {6, 7}
CARD_STATEMENT_DAY = 20  # statement closes on the 20th; payment due on the 28th


def interest(balance: int, annual_pct: float) -> int:
    """Monthly accrual balance * pct / 1200, rounded half-up to whole dollars (PNC rule)."""
    value = Decimal(balance) * Decimal(str(annual_pct)) / Decimal(1200)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def month_periods(as_of: date, months: int) -> list[date]:
    if as_of.day != calendar.monthrange(as_of.year, as_of.month)[1]:
        raise ValueError("as_of must be a month-end date")
    end = as_of.year * 12 + as_of.month - 1
    return [date(i // 12, i % 12 + 1, 1) for i in range(end - months + 1, end + 1)]


def _on(period: date, day: int) -> date:
    return period.replace(day=min(day, calendar.monthrange(period.year, period.month)[1]))


def _split(total: int, parts: int, rng: random.Random) -> list[int]:
    """Split a whole-dollar total into `parts` positive whole-dollar pieces."""
    parts = max(1, min(parts, total))
    weights = [rng.uniform(0.6, 1.4) for _ in range(parts)]
    scale = sum(weights)
    pieces = [max(1, int(total * w / scale)) for w in weights]
    pieces[-1] += total - sum(pieces)
    if pieces[-1] < 1:  # rebalance tiny remainders
        pieces = [total // parts] * parts
        pieces[-1] += total - sum(pieces)
    return pieces


class _Ledger:
    def __init__(self):
        self.events: list[dict] = []
        self._serial = 0

    def add(self, acct, when, ttype, category, description, amount, sign, flow,
            transfer_id="", merchant=None, bill=None):
        if amount <= 0:
            return
        self._serial += 1
        self.events.append(dict(
            account=acct, date=when, transaction_type=ttype, category=category,
            description=description, amount=int(amount), change=sign * int(amount),
            flow_class=flow, transfer_id=transfer_id, merchant_key=merchant, bill_key=bill,
            serial=self._serial))

    def transfer(self, src, dst, dst_is_liability, when, category, amount, tid, desc_out, desc_in):
        """Both legs of an internal transfer (shared transfer_id), PNC `paired()` style."""
        self.add(src, when, "payment" if dst_is_liability else "transfer_out", category,
                 desc_out, amount, -1, "internal_transfer", tid)
        self.add(dst, when, "payment" if dst_is_liability else "transfer_in", category,
                 desc_in, amount, -1 if dst_is_liability else 1, "internal_transfer", tid)


def _order_key(e):
    # Same-day credits before debits so intraday ordering never fakes an overdraft.
    return (e["date"], 0 if e["change"] > 0 else 1, e["serial"])


def generate_student(persona: Persona, as_of: date = DEFAULT_AS_OF,
                     months: int = DEFAULT_MONTHS) -> StudentProfile:
    rng = random.Random(persona.seed)
    pid = persona.profile_id
    periods = month_periods(as_of, months)
    start = periods[0]
    city = CITIES[persona.city]
    catalog = MERCHANTS[persona.city]

    ids = {"checking": f"{pid}-checking", "savings": f"{pid}-savings"}
    if persona.card_limit:
        ids["credit_card"] = f"{pid}-credit-card"
    if persona.student_loan_opening:
        ids["student_loan"] = f"{pid}-student-loan"
    if persona.auto_loan_opening:
        ids["auto_loan"] = f"{pid}-auto-loan"
    auto_payment = (int(round(_amortized_payment(persona.auto_loan_opening, persona.auto_loan_apr_pct / 100,
                                                 persona.auto_loan_term_months)))
                    if persona.auto_loan_opening else 0)

    led = _Ledger()
    used_merchants: set[tuple[str, str, str]] = set()
    savings_bal = persona.savings_opening
    card_bal = persona.card_opening
    card_paid_in_full = persona.card_payoff_ratio >= 1.0
    sl_bal = persona.student_loan_opening
    auto_bal = persona.auto_loan_opening
    goal_contributions = 0

    for period in periods:
        ym = period.strftime("%Y-%m")
        # Income ------------------------------------------------------------
        if persona.job_monthly:
            factor = persona.summer_job_factor if period.month in SUMMER_MONTHS else 1.0
            for day in (1, 15):
                pay = int(round(persona.job_monthly * factor / 2 * rng.uniform(0.94, 1.06)))
                led.add("checking", _on(period, day), "paycheck", "payroll",
                        f"Payroll - {persona.employer}", pay, 1, "income")
        if persona.family_support:
            led.add("checking", _on(period, 3), "deposit", "family_support",
                    "Family support transfer", persona.family_support, 1, "income")
        if ym in persona.aid_lump_sums:
            led.add("checking", _on(period, 20), "deposit", "financial_aid",
                    f"Financial aid refund - {persona.school}", persona.aid_lump_sums[ym], 1, "income")

        # Recurring bills (paid from checking) ------------------------------
        for b in persona.bills:
            led.add("checking", _on(period, b.day), "payment", b.category, b.payee,
                    b.amount, -1, "expense", bill=f"{pid}-bill-{b.key}")
        if persona.cash_withdrawal:
            led.add("checking", _on(period, 9), "withdrawal", "cash", "ATM cash withdrawal",
                    persona.cash_withdrawal, -1, "expense")

        # Discretionary purchases (merchant-linked) -------------------------
        card_purchases = 0  # posted on or before the statement close
        card_after_close = 0  # posted after close: billed next month
        for spec in persona.spending:
            total = int(round(spec.monthly_budget * rng.uniform(0.85, 1.15))) + spec.month_extra.get(ym, 0)
            for amount in _split(total, spec.count, rng):
                name = rng.choice(catalog[spec.category])
                mkey = merchant_key(persona.city, name)
                used_merchants.add((mkey, name, spec.category))
                on_card = "credit_card" in ids and rng.random() < persona.card_share
                acct = "credit_card" if on_card else "checking"
                day = rng.randint(2, 28)
                led.add(acct, _on(period, day), "purchase", spec.category, name,
                        amount, 1 if on_card else -1, "expense", merchant=mkey)
                if on_card and day <= CARD_STATEMENT_DAY:
                    card_purchases += amount
                elif on_card:
                    card_after_close += amount

        # Goal contribution: checking -> savings ----------------------------
        if persona.goal_monthly:
            led.transfer("checking", "savings", False, _on(period, 16), "goal_contribution",
                         persona.goal_monthly, f"X-{pid}-{ym}-goal",
                         f"Transfer to savings - {persona.goal_name}",
                         f"Transfer from checking - {persona.goal_name}")
            savings_bal += persona.goal_monthly
            goal_contributions += persona.goal_monthly
        accrued = interest(savings_bal, persona.savings_apy_pct)
        led.add("savings", _on(period, 31), "interest_accrual", "asset_interest",
                "Savings interest", accrued, 1, "non_cash")
        savings_bal += accrued

        # Credit card: interest on carried balance, then payment ------------
        if "credit_card" in ids:
            card_interest = 0 if card_paid_in_full else interest(card_bal, persona.card_apr_pct)
            led.add("credit_card", _on(period, 26), "interest_accrual", "debt_interest",
                    "Card interest charge", card_interest, 1, "non_cash")
            due = card_bal + card_purchases + card_interest
            if persona.card_payoff_ratio >= 1.0:
                payment = due
            else:
                payment = min(due, max(25, int(round(due * persona.card_payoff_ratio))))
            led.transfer("checking", "credit_card", True, _on(period, 28), "credit_card_payment",
                         payment, f"X-{pid}-{ym}-card", "Credit card payment", "Payment received - thank you")
            card_paid_in_full = payment == due
            card_bal = due - payment + card_after_close

        # Loans ---------------------------------------------------------------
        if "student_loan" in ids and not persona.student_loan_subsidized:
            accrued = interest(sl_bal, persona.student_loan_apr_pct)
            led.add("student_loan", _on(period, 20), "interest_accrual", "debt_interest",
                    "Unsubsidized interest (in-school deferment)", accrued, 1, "non_cash")
            sl_bal += accrued
        if "auto_loan" in ids:
            accrued = interest(auto_bal, persona.auto_loan_apr_pct)
            led.add("auto_loan", _on(period, 20), "interest_accrual", "debt_interest",
                    "Auto loan interest", accrued, 1, "non_cash")
            led.transfer("checking", "auto_loan", True, _on(period, 21), "auto_loan_payment",
                         auto_payment, f"X-{pid}-{ym}-auto", "Auto loan payment", "Auto loan payment received")
            auto_bal += accrued - auto_payment

    # Checking opening: raise only as much as needed to stay above the floor.
    checking_events = sorted((e for e in led.events if e["account"] == "checking"), key=_order_key)
    running = low = 0
    for e in checking_events:
        running += e["change"]
        low = min(low, running)
    checking_opening = max(persona.checking_opening, CHECKING_FLOOR - low)

    openings = {"checking": checking_opening, "savings": persona.savings_opening,
                "credit_card": persona.card_opening, "student_loan": persona.student_loan_opening,
                "auto_loan": persona.auto_loan_opening}

    # Build ledger rows, running balances and statements -------------------
    balances = {k: openings[k] for k in ids}
    transactions: list[Transaction] = []
    monthly = defaultdict(lambda: {"inc": 0, "dec": 0, "count": 0})
    month_open: dict[tuple[str, str], int] = {}
    for n, e in enumerate(sorted(led.events, key=_order_key), start=1):
        kind = e["account"]
        ym = e["date"].strftime("%Y-%m")
        month_open.setdefault((kind, ym), balances[kind])
        balances[kind] += e["change"]
        if balances[kind] < 0:
            raise ValueError(f"{pid}: negative {kind} balance on {e['date']}")
        stats = monthly[(kind, ym)]
        stats["inc" if e["change"] > 0 else "dec"] += abs(e["change"])
        stats["count"] += 1
        transactions.append(Transaction(
            transaction_id=f"{pid}-T{n:05d}", account_id=ids[kind], account_type=kind,
            posted_date=e["date"], transaction_type=e["transaction_type"], category=e["category"],
            description=e["description"], amount=e["amount"], balance_change=e["change"],
            balance_after=balances[kind], flow_class=e["flow_class"], transfer_id=e["transfer_id"],
            merchant_key=e["merchant_key"], bill_key=e["bill_key"]))

    statements, carry = [], dict(openings)
    for kind in ids:
        for period in periods:
            ym = period.strftime("%Y-%m")
            s = monthly[(kind, ym)]
            opening = month_open.get((kind, ym), carry[kind])
            closing = opening + s["inc"] - s["dec"]
            statements.append(MonthlyStatement(
                account_id=ids[kind], account_type=kind, month=ym, opening_balance=opening,
                balance_increases=s["inc"], balance_decreases=s["dec"], closing_balance=closing,
                transaction_count=s["count"]))
            carry[kind] = closing

    if "credit_card" in ids and balances["credit_card"] > persona.card_limit:
        raise ValueError(f"{pid}: card balance exceeds limit")

    accounts = [Account(
        account_id=ids["checking"], account_type="checking", name="Student Checking",
        balance=balances["checking"], opening_balance=checking_opening,
        history_start=start, as_of_date=as_of)]
    accounts.append(Account(
        account_id=ids["savings"], account_type="savings", name="Goal Savings",
        balance=balances["savings"], opening_balance=persona.savings_opening,
        annual_yield_pct=persona.savings_apy_pct, history_start=start, as_of_date=as_of))
    if "credit_card" in ids:
        bal = balances["credit_card"]
        accounts.append(Account(
            account_id=ids["credit_card"], account_type="credit_card", name="Student Rewards Card",
            balance=bal, opening_balance=persona.card_opening, apr_pct=persona.card_apr_pct,
            credit_limit=persona.card_limit, monthly_payment=min(bal, max(25, int(round(bal * 0.03)))),
            history_start=start, as_of_date=as_of))
    if "student_loan" in ids:
        bal = balances["student_loan"]
        accounts.append(Account(
            account_id=ids["student_loan"], account_type="student_loan",
            name=("Subsidized" if persona.student_loan_subsidized else "Unsubsidized") + " Federal Student Loan",
            balance=bal, opening_balance=persona.student_loan_opening, apr_pct=persona.student_loan_apr_pct,
            monthly_payment=0, loan_status="in_school_deferment", subsidized=persona.student_loan_subsidized,
            repayment_monthly_payment_estimate=int(round(_amortized_payment(bal, persona.student_loan_apr_pct / 100, 120))),
            history_start=start, as_of_date=as_of))
    if "auto_loan" in ids:
        accounts.append(Account(
            account_id=ids["auto_loan"], account_type="auto_loan", name="Auto Loan",
            balance=balances["auto_loan"], opening_balance=persona.auto_loan_opening,
            apr_pct=persona.auto_loan_apr_pct, monthly_payment=auto_payment, loan_status="repayment",
            history_start=start, as_of_date=as_of))

    streams = []
    if persona.job_monthly:
        streams.append(IncomeStream(source="internship" if "intern" in (persona.role or "") else "job",
                                    payer=persona.employer, monthly_amount=persona.job_monthly))
    if persona.family_support:
        streams.append(IncomeStream(source="family_support", payer=persona.family_payer,
                                    monthly_amount=persona.family_support))
    if persona.aid_lump_sums:
        streams.append(IncomeStream(source="financial_aid", payer=persona.school,
                                    lump_sums=dict(persona.aid_lump_sums)))
    summer = sum(1 for p in periods if p.month in SUMMER_MONTHS)
    job_avg = persona.job_monthly * (months - summer + summer * persona.summer_job_factor) / months
    planned_income = int(round(job_avg + persona.family_support + sum(persona.aid_lump_sums.values()) / months))
    planned_spend = int(round(
        sum(b.amount for b in persona.bills) + persona.cash_withdrawal
        + sum(s.monthly_budget + sum(s.month_extra.values()) / months for s in persona.spending)))

    merchants = []
    for mkey, name, category in sorted(used_merchants):
        mr = random.Random(mkey)
        merchants.append(Merchant(
            merchant_key=mkey, name=name, category=category, street_number=str(mr.randint(100, 3999)),
            street_name=mr.choice(city["streets"]), city=persona.city, state=city["state"], zip=city["zip"],
            lat=round(city["lat"] + mr.uniform(-0.03, 0.03), 5), lng=round(city["lng"] + mr.uniform(-0.03, 0.03), 5)))

    bills = [RecurringBill(bill_key=f"{pid}-bill-{b.key}", payee=b.payee, nickname=b.nickname, category=b.category,
                           amount=b.amount, day_of_month=b.day, account_id=ids["checking"]) for b in persona.bills]

    goal = Goal(
        goal_id=f"{pid}-goal", name=persona.goal_name, goal_type=persona.goal_type,
        target_amount=persona.goal_target, initial_saved=persona.goal_initial,
        current_saved=persona.goal_initial + goal_contributions, monthly_contribution=persona.goal_monthly,
        target_date=date.fromisoformat(persona.goal_target_date), linked_account_id=ids["savings"],
        created_date=start)

    student = StudentInfo(
        school=persona.school, city=persona.city, state=city["state"], class_year=persona.class_year,
        major=persona.major, living_situation=persona.living_situation,
        employment=Employment(employer=persona.employer, role=persona.role, hours_per_week=persona.hours_per_week)
        if persona.employer else None)

    return StudentProfile(
        profile_id=pid, persona_key=persona.key, is_primary_demo=persona.primary, seed=persona.seed,
        generator=GENERATOR, history_start=start, as_of_date=as_of, student=student,
        assumptions=Assumptions(monthly_income=planned_income, monthly_non_debt_expenses=planned_spend,
                                credit_limit=persona.card_limit, income_streams=streams),
        accounts=accounts, transactions=transactions, bills=bills, merchants=merchants,
        statements=statements, goal=goal,
        field_sources={
            "student": Origin.PNC_GENERATED, "assumptions": Origin.PNC_GENERATED,
            "accounts": Origin.PNC_GENERATED, "accounts[checking].opening_balance": Origin.DERIVED,
            "accounts[*].balance": Origin.DERIVED, "transactions": Origin.PNC_GENERATED,
            "transactions[*].balance_after": Origin.DERIVED, "statements": Origin.DERIVED,
            "bills": Origin.PNC_GENERATED, "merchants": Origin.WAYPOINT_GENERATED,
            "goal": Origin.PNC_GENERATED, "goal.current_saved": Origin.DERIVED,
        })


def generate_all(as_of: date = DEFAULT_AS_OF, months: int = DEFAULT_MONTHS) -> list[StudentProfile]:
    return [generate_student(p, as_of, months) for p in PERSONAS]


def liability(account_type: str) -> bool:
    return account_type in LIABILITY_TYPES
