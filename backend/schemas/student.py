"""Synthetic student profile in PNC ledger conventions (whole dollars).

Mirrors the PNC Lab_Package data model (profiles / accounts / transactions /
monthly_statements) with student-specific additions: student info, recurring bills,
merchant references and one primary goal.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Dollars, Origin

AccountType = Literal["checking", "savings", "credit_card", "student_loan", "auto_loan"]
ASSET_TYPES = frozenset({"checking", "savings"})
LIABILITY_TYPES = frozenset({"credit_card", "student_loan", "auto_loan"})
LOAN_TYPES = frozenset({"student_loan", "auto_loan"})

# Same flow classes as PNC Lab_Package/data/README.md.
FlowClass = Literal["income", "expense", "internal_transfer", "external_transfer", "non_cash"]
TransactionType = Literal[
    "paycheck", "deposit", "withdrawal", "payment", "purchase",
    "transfer_out", "transfer_in", "interest_accrual", "fee",
]
IncomeSource = Literal["job", "internship", "family_support", "financial_aid"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Employment(_Model):
    employer: str
    role: str
    hours_per_week: int
    pay_frequency: Literal["semi_monthly"] = "semi_monthly"


class StudentInfo(_Model):
    school: str
    city: str
    state: str
    class_year: Literal["freshman", "sophomore", "junior", "senior"]
    major: str
    enrollment: Literal["full_time", "part_time"] = "full_time"
    living_situation: str
    employment: Employment | None = None


class IncomeStream(_Model):
    source: IncomeSource
    payer: str
    monthly_amount: Dollars = 0
    lump_sums: dict[str, Dollars] = Field(default_factory=dict, description="YYYY-MM -> amount")


class Assumptions(_Model):
    """PNC profiles.csv equivalent: planning assumptions, not observed values."""

    monthly_income: Dollars
    monthly_non_debt_expenses: Dollars
    credit_limit: Dollars = 0
    income_streams: list[IncomeStream]


class Account(_Model):
    account_id: str
    account_type: AccountType
    name: str
    balance: Dollars = Field(description="Closing balance at as_of_date (positive for liabilities)")
    opening_balance: Dollars
    monthly_payment: Dollars = 0
    apr_pct: float = 0.0
    annual_yield_pct: float = 0.0
    credit_limit: Dollars | None = None
    loan_status: str | None = None
    subsidized: bool | None = None
    repayment_monthly_payment_estimate: Dollars | None = None
    history_start: date
    as_of_date: date


class Transaction(_Model):
    transaction_id: str
    account_id: str
    account_type: AccountType
    posted_date: date
    transaction_type: TransactionType
    category: str
    description: str
    amount: Dollars = Field(gt=0)
    balance_change: Dollars
    balance_after: Dollars
    flow_class: FlowClass
    transfer_id: str = ""
    merchant_key: str | None = None
    bill_key: str | None = None


class RecurringBill(_Model):
    bill_key: str
    payee: str
    nickname: str
    category: str
    amount: Dollars = Field(gt=0)
    day_of_month: int = Field(ge=1, le=28)
    account_id: str


class Merchant(_Model):
    merchant_key: str
    name: str
    category: str
    street_number: str
    street_name: str
    city: str
    state: str
    zip: str
    lat: float
    lng: float


class MonthlyStatement(_Model):
    account_id: str
    account_type: AccountType
    month: str
    opening_balance: Dollars
    balance_increases: Dollars
    balance_decreases: Dollars
    closing_balance: Dollars
    transaction_count: int


class Goal(_Model):
    goal_id: str
    name: str
    goal_type: Literal["emergency_fund", "vehicle", "tuition", "relocation", "other"]
    target_amount: Dollars = Field(gt=0)
    initial_saved: Dollars = Field(ge=0, description="Earmarked at history_start")
    current_saved: Dollars = Field(ge=0, description="initial_saved + goal contributions in history")
    monthly_contribution: Dollars = Field(ge=0)
    target_date: date
    linked_account_id: str
    created_date: date


class StudentProfile(_Model):
    schema_version: int = 1
    profile_id: str
    persona_key: str
    is_primary_demo: bool
    seed: int
    generator: str
    history_start: date
    as_of_date: date
    student: StudentInfo
    assumptions: Assumptions
    accounts: list[Account]
    transactions: list[Transaction]
    bills: list[RecurringBill]
    merchants: list[Merchant]
    statements: list[MonthlyStatement]
    goal: Goal
    field_sources: dict[str, Origin]

    def account(self, account_id: str) -> Account:
        return next(a for a in self.accounts if a.account_id == account_id)

    def account_of_type(self, account_type: str) -> Account | None:
        return next((a for a in self.accounts if a.account_type == account_type), None)
