"""Student persona definitions: planning assumptions that drive the generator.

All amounts are whole dollars per month unless stated otherwise. Payee and employer
names are fictional.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BillSpec:
    key: str
    payee: str
    nickname: str
    category: str
    amount: int
    day: int


@dataclass(frozen=True)
class SpendSpec:
    category: str
    monthly_budget: int
    count: int
    month_extra: dict = field(default_factory=dict)  # "YYYY-MM" -> extra dollars


@dataclass(frozen=True)
class Persona:
    key: str
    profile_id: str
    seed: int
    primary: bool
    # student info
    school: str
    city: str
    class_year: str
    major: str
    living_situation: str
    employer: str | None
    role: str | None
    hours_per_week: int
    # income
    job_monthly: int
    summer_job_factor: float
    family_support: int
    family_payer: str | None
    aid_lump_sums: dict
    # balances at history_start
    checking_opening: int
    savings_opening: int
    savings_apy_pct: float
    # card
    card_limit: int = 0
    card_opening: int = 0
    card_apr_pct: float = 0.0
    card_share: float = 0.0
    card_payoff_ratio: float = 1.0
    # loans
    student_loan_opening: int = 0
    student_loan_apr_pct: float = 0.0
    student_loan_subsidized: bool = False
    auto_loan_opening: int = 0
    auto_loan_apr_pct: float = 0.0
    auto_loan_term_months: int = 48
    # spending
    bills: tuple = ()
    spending: tuple = ()
    cash_withdrawal: int = 0
    # goal
    goal_name: str = ""
    goal_type: str = "other"
    goal_target: int = 0
    goal_initial: int = 0
    goal_monthly: int = 0
    goal_target_date: str = ""
    # Optional fixed customer name (otherwise generated in mapping/missing_fields.py)
    first_name: str | None = None
    last_name: str | None = None


PERSONAS = (
    Persona(
        key="utd_junior_cs", profile_id="stu-001", seed=1001, primary=True,
        school="The University of Texas at Dallas", city="Richardson", class_year="junior",
        major="Computer Science", living_situation="shared off-campus apartment",
        employer="Comet Campus Library", role="library assistant", hours_per_week=18,
        job_monthly=1350, summer_job_factor=1.2, family_support=250, family_payer="Family support",
        aid_lump_sums={},
        checking_opening=640, savings_opening=900, savings_apy_pct=4.0,
        card_limit=1500, card_opening=180, card_apr_pct=24.99, card_share=0.45, card_payoff_ratio=1.0,
        student_loan_opening=9500, student_loan_apr_pct=6.53, student_loan_subsidized=False,
        bills=(
            BillSpec("rent", "Campus Pointe Apartments", "Rent (my share)", "housing", 725, 1),
            BillSpec("renters-insurance", "Shield Renters Insurance", "Renter's insurance", "insurance", 15, 5),
            BillSpec("internet", "Prairie Fiber Internet", "Internet (split)", "utilities", 30, 8),
            BillSpec("phone", "Lone Star Mobile", "Phone plan", "phone", 40, 12),
            BillSpec("streaming", "StreamBox", "Streaming", "subscriptions", 12, 18),
        ),
        spending=(
            SpendSpec("groceries", 220, 6), SpendSpec("dining", 110, 5), SpendSpec("coffee", 35, 5),
            SpendSpec("transport", 70, 3), SpendSpec("shopping", 60, 2), SpendSpec("entertainment", 30, 1),
            SpendSpec("school_supplies", 20, 1, {"2026-08": 180}),
        ),
        goal_name="Emergency fund", goal_type="emergency_fund", goal_target=3000,
        goal_initial=600, goal_monthly=150, goal_target_date="2027-08-31",
    ),
    Persona(
        key="unt_sophomore_business", profile_id="stu-002", seed=1002, primary=False,
        school="University of North Texas", city="Denton", class_year="sophomore",
        major="Business Administration", living_situation="living with parents",
        employer="Square Deal Market", role="retail sales associate", hours_per_week=20,
        job_monthly=1150, summer_job_factor=1.35, family_support=0, family_payer=None, aid_lump_sums={},
        checking_opening=450, savings_opening=2100, savings_apy_pct=3.5,
        bills=(
            BillSpec("car-insurance", "Bluebonnet Auto Insurance", "Car insurance", "insurance", 95, 4),
            BillSpec("phone", "Lone Star Mobile", "Phone (family plan share)", "phone", 35, 10),
            BillSpec("gym", "Eagle Fitness Club", "Gym membership", "subscriptions", 25, 15),
            BillSpec("streaming", "StreamBox", "Streaming", "subscriptions", 11, 20),
        ),
        spending=(
            SpendSpec("transport", 120, 4), SpendSpec("dining", 140, 6), SpendSpec("coffee", 30, 4),
            SpendSpec("shopping", 110, 3), SpendSpec("entertainment", 50, 2), SpendSpec("groceries", 60, 2),
        ),
        first_name="Poyo", last_name="de Avon",  # demo login user
        goal_name="First car fund", goal_type="vehicle", goal_target=6000,
        goal_initial=1800, goal_monthly=400, goal_target_date="2027-12-31",
    ),
    Persona(
        key="tamu_senior_engineering", profile_id="stu-003", seed=1003, primary=False,
        school="Texas A&M University", city="College Station", class_year="senior",
        major="Mechanical Engineering", living_situation="one-bedroom apartment",
        employer="Brazos Engineering Co-op", role="engineering co-op intern", hours_per_week=30,
        job_monthly=2600, summer_job_factor=1.0, family_support=0, family_payer=None, aid_lump_sums={},
        checking_opening=1100, savings_opening=650, savings_apy_pct=4.0,
        card_limit=4000, card_opening=1900, card_apr_pct=26.49, card_share=0.6, card_payoff_ratio=0.35,
        auto_loan_opening=9800, auto_loan_apr_pct=7.4, auto_loan_term_months=48,
        bills=(
            BillSpec("rent", "Northgate Flats", "Rent", "housing", 850, 1),
            BillSpec("car-insurance", "Bluebonnet Auto Insurance", "Car insurance", "insurance", 120, 6),
            BillSpec("utilities", "Brazos Power & Water", "Utilities", "utilities", 85, 9),
            BillSpec("internet", "Prairie Fiber Internet", "Internet", "utilities", 45, 11),
            BillSpec("phone", "Lone Star Mobile", "Phone plan", "phone", 55, 14),
            BillSpec("streaming", "StreamBox", "Streaming", "subscriptions", 16, 22),
        ),
        spending=(
            SpendSpec("groceries", 280, 6), SpendSpec("dining", 220, 7), SpendSpec("transport", 110, 4),
            SpendSpec("shopping", 180, 3), SpendSpec("entertainment", 90, 2), SpendSpec("coffee", 40, 4),
        ),
        goal_name="Post-graduation relocation fund", goal_type="relocation", goal_target=2500,
        goal_initial=400, goal_monthly=200, goal_target_date="2027-05-31",
    ),
    Persona(
        key="utaustin_freshman_bio", profile_id="stu-004", seed=1004, primary=False,
        school="The University of Texas at Austin", city="Austin", class_year="freshman",
        major="Biology", living_situation="on-campus residence hall",
        employer="Forty Acres Dining Hall", role="dining hall attendant", hours_per_week=12,
        job_monthly=600, summer_job_factor=1.0, family_support=150, family_payer="Family support",
        aid_lump_sums={"2026-08": 1800},
        checking_opening=300, savings_opening=250, savings_apy_pct=3.0,
        card_limit=800, card_opening=120, card_apr_pct=22.99, card_share=0.5, card_payoff_ratio=0.6,
        student_loan_opening=5500, student_loan_apr_pct=4.99, student_loan_subsidized=True,
        bills=(
            BillSpec("phone", "Lone Star Mobile", "Phone plan", "phone", 30, 7),
            BillSpec("streaming", "StreamBox", "Streaming (student)", "subscriptions", 10, 19),
        ),
        spending=(
            SpendSpec("dining", 170, 6), SpendSpec("coffee", 50, 6), SpendSpec("shopping", 120, 3),
            SpendSpec("entertainment", 60, 2), SpendSpec("groceries", 50, 2), SpendSpec("transport", 45, 3),
            SpendSpec("school_supplies", 20, 1, {"2026-08": 350}),
        ),
        cash_withdrawal=40,
        goal_name="Spring tuition gap", goal_type="tuition", goal_target=2000,
        goal_initial=150, goal_monthly=100, goal_target_date="2027-01-10",
    ),
)
