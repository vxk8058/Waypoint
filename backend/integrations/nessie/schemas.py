"""Response models for Nessie records (live API shapes). Unknown fields are kept."""
from pydantic import BaseModel, ConfigDict, Field


class _Rec(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(alias="_id")


class NessieCustomer(_Rec):
    first_name: str
    last_name: str
    address: dict = Field(default_factory=dict)


class NessieAccount(_Rec):
    type: str
    nickname: str = ""
    rewards: int = 0
    balance: float
    account_number: str | None = None
    customer_id: str | None = None


class NessieDeposit(_Rec):
    transaction_date: str
    amount: float
    status: str | None = None
    medium: str | None = None
    description: str = ""


class NessieWithdrawal(NessieDeposit):
    pass


class NessieTransfer(NessieDeposit):
    pass


class NessiePurchase(_Rec):
    purchase_date: str
    amount: float
    merchant_id: str | None = None
    status: str | None = None
    medium: str | None = None
    description: str = ""


class NessieBill(_Rec):
    payee: str
    payment_amount: float
    status: str
    nickname: str = ""
    recurring_date: int | None = None
    payment_date: str | None = None
    upcoming_payment_date: str | None = None
    account_id: str | None = None


class NessieLoan(_Rec):
    type: str
    amount: float
    monthly_payment: float = 0
    status: str | None = None
    credit_score: int | None = None
    description: str = ""


class NessieMerchant(_Rec):
    name: str
    category: str | list[str] | None = None
    address: dict | None = None
    geocode: dict | None = None


CHILD_MODELS = {"deposit": NessieDeposit, "withdrawal": NessieWithdrawal, "purchase": NessiePurchase,
                "transfer": NessieTransfer, "bill": NessieBill, "loan": NessieLoan}
