"""Nessie create-request bodies, verified against the LIVE API (prod-api.nessieisreal.com)
during Phase 1 - not just the published YAML, which is incomplete:

- POST responses include `objectCreated` with `_id` (spec says a plain string).
- Purchases and transfers can be created (not in the spec). Purchases use `purchase_date`.
- TransferCreate rejects `medium` and `payee_id` ("extra fields not permitted").
- Amounts/balances are integers; decimals are silently truncated.
- Transactions never change account balances; PUT /accounts ignores `balance`.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Address(_Body):
    street_number: str
    street_name: str
    city: str
    state: str
    zip: str


class Geocode(_Body):
    lat: float
    lng: float


class CustomerCreate(_Body):
    first_name: str
    last_name: str
    address: Address


class AccountCreate(_Body):
    type: Literal["Checking", "Savings", "Credit Card"]
    nickname: str
    rewards: int = Field(ge=0)
    balance: int = Field(ge=0)


class MerchantCreate(_Body):
    name: str
    category: str
    address: Address
    geocode: Geocode


class DepositCreate(_Body):
    medium: Literal["balance"]
    transaction_date: str
    status: Literal["pending", "completed", "cancelled"]
    amount: int = Field(gt=0)
    description: str


class WithdrawalCreate(DepositCreate):
    pass


class PurchaseCreate(_Body):
    merchant_id: str
    medium: Literal["balance"]
    purchase_date: str
    status: Literal["pending", "completed", "cancelled"]
    amount: int = Field(gt=0)
    description: str


class TransferCreate(_Body):
    transaction_date: str
    status: Literal["pending", "completed", "cancelled"]
    amount: int = Field(gt=0)
    description: str


class BillCreate(_Body):
    status: Literal["pending", "cancelled", "completed", "recurring"]
    payee: str
    nickname: str
    payment_date: str
    recurring_date: int = Field(ge=1, le=31)
    payment_amount: int = Field(gt=0)


class LoanCreate(_Body):
    type: str
    status: str
    credit_score: int = Field(ge=300, le=850)
    monthly_payment: int = Field(ge=0)
    amount: int = Field(gt=0)
    description: str


CREATE_MODELS = {
    "customer": CustomerCreate, "account": AccountCreate, "merchant": MerchantCreate,
    "deposit": DepositCreate, "withdrawal": WithdrawalCreate, "purchase": PurchaseCreate,
    "transfer": TransferCreate, "bill": BillCreate, "loan": LoanCreate,
}

# Endpoint per resource. `{parent}` is filled with the parent's Nessie id at seed time.
CREATE_PATHS = {
    "customer": "/customers",
    "merchant": "/merchants",
    "account": "/customers/{parent}/accounts",
    "loan": "/accounts/{parent}/loans",
    "bill": "/accounts/{parent}/bills",
    "deposit": "/accounts/{parent}/deposits",
    "withdrawal": "/accounts/{parent}/withdrawals",
    "purchase": "/accounts/{parent}/purchases",
    "transfer": "/accounts/{parent}/transfers",
}

# Placeholder for a reference resolved during seeding, e.g. "@ref:stu-001:merchant:m-..."
REF_PREFIX = "@ref:"
