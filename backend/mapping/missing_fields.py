"""Generate Nessie-required fields that PNC-convention profiles do not contain.

Every value is deterministic for a profile (seeded by profile seed) and consistent
with the profile: e.g. card rewards are derived from actual card purchases, the
customer's address is in the student's school city, and the loan credit score sits
in a range typical for a thin student credit file.
"""
import random

from pydantic import BaseModel

from ..generation.catalog import CITIES
from ..schemas.common import Origin
from ..schemas.student import StudentProfile

FIRST_NAMES = ["Maya", "Jordan", "Priya", "Diego", "Avery", "Noah", "Sofia", "Ethan", "Leah", "Marcus",
               "Aaliyah", "Kai", "Elena", "Owen", "Zara", "Lucas"]
LAST_NAMES = ["Rivera", "Patel", "Nguyen", "Okafor", "Bennett", "Chen", "Ramirez", "Thompson", "Alvarez",
              "Kim", "Brooks", "Shah", "Morales", "Hayes", "Ortiz", "Walker"]

CARD_REWARDS_POINTS_PER_DOLLAR = 1  # 1 point per whole dollar of card purchases in history
TRANSACTION_MEDIUM = "balance"
TRANSACTION_STATUS = "completed"  # history is posted; Nessie ignores status for balances anyway
BILL_STATUS = "recurring"


class GeneratedCustomer(BaseModel):
    first_name: str
    last_name: str
    street_number: str
    street_name: str
    city: str
    state: str
    zip: str


class GeneratedLoanFields(BaseModel):
    account_id: str
    loan_type: str
    status: str
    credit_score: int


class GeneratedFields(BaseModel):
    profile_id: str
    customer: GeneratedCustomer
    account_rewards: dict[str, int]
    loans: list[GeneratedLoanFields]
    transaction_medium: str = TRANSACTION_MEDIUM
    transaction_status: str = TRANSACTION_STATUS
    bill_status: str = BILL_STATUS
    field_sources: dict[str, Origin]


def generate_missing_fields(profile: StudentProfile) -> GeneratedFields:
    rng = random.Random(f"{profile.seed}-nessie-fields")
    city = CITIES[profile.student.city]
    customer = GeneratedCustomer(
        first_name=rng.choice(FIRST_NAMES), last_name=rng.choice(LAST_NAMES),
        street_number=str(rng.randint(100, 2999)), street_name=rng.choice(city["streets"]),
        city=profile.student.city, state=city["state"], zip=city["zip"])

    rewards = {}
    for acct in profile.accounts:
        if acct.account_type == "credit_card":
            spent = sum(t.amount for t in profile.transactions
                        if t.account_id == acct.account_id and t.transaction_type == "purchase")
            rewards[acct.account_id] = spent * CARD_REWARDS_POINTS_PER_DOLLAR
        elif acct.account_type in ("checking", "savings"):
            rewards[acct.account_id] = 0

    # Thin-file student credit: better with on-time card history and fewer accounts at risk.
    base = 640 + rng.randint(0, 40)
    card = profile.account_of_type("credit_card")
    if card and card.credit_limit and card.balance / card.credit_limit > 0.3:
        base -= 25
    loans = [GeneratedLoanFields(
        account_id=a.account_id, loan_type="student" if a.account_type == "student_loan" else "auto",
        status=a.loan_status or "active", credit_score=base)
        for a in profile.accounts if a.account_type in ("student_loan", "auto_loan")]

    return GeneratedFields(
        profile_id=profile.profile_id, customer=customer, account_rewards=rewards, loans=loans,
        field_sources={
            "customer.first_name": Origin.WAYPOINT_GENERATED, "customer.last_name": Origin.WAYPOINT_GENERATED,
            "customer.address": Origin.WAYPOINT_GENERATED, "account_rewards": Origin.DERIVED,
            "loans[*].credit_score": Origin.WAYPOINT_GENERATED, "loans[*].status": Origin.PNC_GENERATED,
            "transaction_medium": Origin.WAYPOINT_GENERATED, "transaction_status": Origin.WAYPOINT_GENERATED,
            "bill_status": Origin.WAYPOINT_GENERATED,
        })
