"""Unified Waypoint financial profile.

Phase 2 builds it from the PNC-convention profile (data_mode="pre_seed"). Phase 4 builds
the same shape from Nessie responses plus PNC-only fields (data_mode="nessie").
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel

from .common import Origin, SourceMeta
from .student import StudentInfo


class UnifiedUser(BaseModel):
    profile_id: str
    nessie_customer_id: str | None
    first_name: str
    last_name: str
    address: dict
    student: StudentInfo
    sources: dict[str, Origin]


class UnifiedAccount(BaseModel):
    account_id: str
    type: str
    name: str
    is_liability: bool
    balance: int
    opening_balance: int
    credit_limit: int | None = None
    apr_pct: float = 0.0
    apy_pct: float = 0.0
    monthly_payment: int = 0
    loan_status: str | None = None
    subsidized: bool | None = None
    repayment_monthly_payment_estimate: int | None = None
    nessie_resource: Literal["account", "loan"]
    nessie_local_key: str
    nessie_id: str | None = None
    source: SourceMeta


class UnifiedTransaction(BaseModel):
    transaction_id: str
    account_id: str
    account_type: str
    date: date
    type: str
    category: str
    description: str
    amount: int
    direction: Literal["in", "out"]
    balance_change: int
    flow_class: str
    transfer_id: str = ""
    merchant_key: str | None = None
    merchant_name: str | None = None
    bill_key: str | None = None
    nessie_resource: str | None
    nessie_local_key: str | None
    nessie_id: str | None = None
    source: SourceMeta


class UnifiedBill(BaseModel):
    bill_key: str
    payee: str
    nickname: str
    category: str
    amount: int
    day_of_month: int
    next_due_date: date
    account_id: str
    status: str
    nessie_local_key: str
    nessie_id: str | None = None
    source: SourceMeta


class UnifiedGoal(BaseModel):
    goal_id: str
    name: str
    goal_type: str
    target_amount: int
    current_saved: int
    initial_saved: int
    monthly_contribution: int
    target_date: date
    linked_account_id: str
    created_date: date
    source: SourceMeta


class MonthlySummary(BaseModel):
    month: str
    income: int
    spending: int
    debt_payments: int
    debt_interest: int
    asset_interest: int
    fees: int
    savings_contributions: int
    goal_contributions: int
    net_cash_flow: int
    closing_liquid: int
    closing_assets: int
    closing_debts: int


class WellnessInputs(BaseModel):
    """Raw inputs for the Phase 5 wellness engine (no scores computed here)."""

    history_months: int
    monthly_income_avg: int
    monthly_spending_avg: int
    monthly_recurring_bills: int
    scheduled_monthly_debt_payments: int
    monthly_goal_contribution: int
    liquid_cash: int
    total_assets: int
    total_liabilities: int
    net_worth: int
    credit_card_balance: int
    credit_limit_total: int


class UnifiedProfile(BaseModel):
    schema_version: int = 1
    profile_id: str
    data_mode: Literal["pre_seed", "nessie"]
    history_start: date
    as_of_date: date
    user: UnifiedUser
    accounts: list[UnifiedAccount]
    transactions: list[UnifiedTransaction]
    bills: list[UnifiedBill]
    goal: UnifiedGoal
    monthly_summary: list[MonthlySummary]
    wellness_inputs: WellnessInputs
    pnc_view: dict
    metadata: dict
