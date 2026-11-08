"""Read-only branch data from the existing profile service (fixtures or live data)."""
from typing import Literal

from ..schemas.student import LOAN_TYPES
from ..services.profile_service import ProfileService
from .schemas import Product

Source = Product | Literal["transactions", "bio", "other_api"]


def get_data(profiles: ProfileService, profile_id: str, source: Source, *, refresh: bool = False) -> dict:
    """Use a server-authorized profile ID; leave retrieval failures for the subgraph to handle."""
    if source not in ("checking", "savings", "credit_card", "loans", "transactions", "bio", "other_api"):
        raise ValueError("Unknown banking data source")
    if source == "other_api":
        raise NotImplementedError("No other API source is configured")
    profile = profiles.get(profile_id, refresh=refresh)
    if profile.profile_id != profile_id:
        raise ValueError("Retrieved profile does not match the requested profile")
    data = profile.model_dump(mode="json")
    output = {key: data[key] for key in ("profile_id", "data_mode", "history_start", "as_of_date",
                                   "metadata", "wellness_inputs")}
    if source == "transactions":
        return {**output, "transactions": data["transactions"]}
    if source == "bio":
        return {**output, "student": data["user"]["student"]}

    types = LOAN_TYPES if source == "loans" else {source}
    accounts = [account for account in data["accounts"] if account["type"] in types]
    account_ids = {account["account_id"] for account in accounts}
    output.update(accounts=accounts,
                  transactions=[t for t in data["transactions"] if t["account_id"] in account_ids],
                  bills=[bill for bill in data["bills"] if bill["account_id"] in account_ids])
    if source == "savings" and data["goal"]["linked_account_id"] in account_ids:
        output["goal"] = data["goal"]
    return output
