"""Retrieval layer: fetch everything Waypoint needs about one Nessie customer in one pass.

The rest of the backend reads a `NessieSnapshot`; calculations and agents never call
Nessie themselves. Records that fail response validation are skipped and reported as
warnings instead of breaking the whole profile.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

from .client import NessieClient
from .resources import ACCOUNT_CHILDREN, LIST_PATHS
from .schemas import CHILD_MODELS, NessieAccount, NessieCustomer, NessieMerchant


class AccountActivity(BaseModel):
    deposit: list = Field(default_factory=list)
    withdrawal: list = Field(default_factory=list)
    purchase: list = Field(default_factory=list)
    transfer: list = Field(default_factory=list)
    bill: list = Field(default_factory=list)
    loan: list = Field(default_factory=list)


class NessieSnapshot(BaseModel):
    customer: NessieCustomer
    accounts: list[NessieAccount]
    activity: dict[str, AccountActivity]  # account id -> records
    merchants: dict[str, NessieMerchant]
    fetched_at: datetime
    api_calls: int
    warnings: list[str] = Field(default_factory=list)


class NessieGateway:
    def __init__(self, client: NessieClient, max_workers: int = 6):
        self.client, self.max_workers = client, max_workers

    def _validate(self, model, rows, label, warnings):
        out = []
        for row in rows:
            try:
                out.append(model.model_validate(row))
            except ValidationError as exc:
                warnings.append(f"skipped invalid {label} {row.get('_id', '?')}: {exc.errors()[0]['msg']}")
        return out

    def get_customer(self, customer_id: str) -> NessieCustomer:
        return NessieCustomer.model_validate(self.client.get(f"/customers/{customer_id}"))

    def list_accounts(self, customer_id: str) -> list[dict]:
        return self.client.list(LIST_PATHS["account"].format(parent=customer_id))

    def list_children(self, account_id: str, resource: str) -> list[dict]:
        return self.client.list(LIST_PATHS[resource].format(parent=account_id))

    def fetch_customer(self, customer_id: str) -> NessieSnapshot:
        calls_before = self.client.calls
        warnings: list[str] = []
        customer = self.get_customer(customer_id)
        accounts = self._validate(NessieAccount, self.list_accounts(customer_id), "account", warnings)

        jobs = [(a.id, r) for a in accounts for r in ACCOUNT_CHILDREN]
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            results = list(pool.map(lambda job: self.list_children(*job), jobs))
        activity = {a.id: AccountActivity() for a in accounts}
        for (acct_id, resource), rows in zip(jobs, results):
            setattr(activity[acct_id], resource, self._validate(CHILD_MODELS[resource], rows, resource, warnings))

        needed = {p.merchant_id for act in activity.values() for p in act.purchase if p.merchant_id}
        merchants = {}
        if needed:
            for m in self._validate(NessieMerchant, self.client.list(LIST_PATHS["merchant"]), "merchant", warnings):
                if m.id in needed:
                    merchants[m.id] = m
            for mid in needed - merchants.keys():  # not in the key's merchant list: fetch directly
                row = self.client.get_or_none(f"/merchants/{mid}")
                if row:
                    merchants[mid] = NessieMerchant.model_validate(row)
                else:
                    warnings.append(f"merchant {mid} referenced by purchases was not found")
        return NessieSnapshot(customer=customer, accounts=accounts, activity=activity, merchants=merchants,
                              fetched_at=datetime.now(timezone.utc), api_calls=self.client.calls - calls_before,
                              warnings=warnings)
