"""Chart datasets and headline facts computed in code from trusted product results (whole dollars)."""
import calendar
import statistics
from collections import defaultdict
from datetime import date, timedelta


def _label(slug: str) -> str:
    return slug.replace("_", " ").capitalize()


def _month(month: str) -> str:
    year, number = month.split("-")
    return f"{calendar.month_name[int(number)]} {year}"


def month_after(month: str) -> str:
    year, number = map(int, month.split("-"))
    return f"{year + number // 12}-{number % 12 + 1:02d}"


def _transactions(results) -> list[dict]:
    by_id = {}
    for result in results:
        txns = result.data.get("transactions", [])
        if isinstance(txns, dict):  # Other Data nests the source payload under its name.
            txns = txns.get("transactions", [])
        for txn in txns:
            by_id[txn["transaction_id"]] = txn  # The same transaction can arrive from two branches.
    return sorted(by_id.values(), key=lambda t: t["date"])


def build_datasets(results) -> dict[str, dict]:
    txns = _transactions(results)
    scope = ", ".join(sorted({_label(t["account_type"]).lower() for t in txns}))
    spending, income = defaultdict(lambda: defaultdict(int)), defaultdict(int)
    for txn in txns:
        month, signed = txn["date"][:7], txn["amount"] if txn["direction"] == "out" else -txn["amount"]
        # Transfers and card/loan payments are internal_transfer and interest is non_cash, so neither is spending.
        if txn["flow_class"] == "expense":
            spending[month][txn["category"]] += signed  # an inbound expense is a refund and reduces spending
        elif txn["flow_class"] == "income":
            income[month] -= signed
    months = sorted(set(spending) | set(income))
    datasets = {}
    for month in months:
        items = sorted(((c, v) for c, v in spending[month].items() if v > 0), key=lambda cv: -cv[1])
        if items:
            datasets[f"spending_by_category.{month}"] = {
                "description": f"Spending by category, {_month(month)} ({scope} transactions)",
                "keys": [c for c, _ in items], "categories": [_label(c) for c, _ in items],
                "series": [{"name": "Spent", "values": [v for _, v in items]}], "kind": "category",
            }
    if months:
        datasets["income_vs_spending"] = {
            "description": f"Income and net spending by month ({scope} transactions)",
            "keys": months, "categories": [_month(m) for m in months],
            "series": [{"name": "Income", "values": [income[m] for m in months]},
                       {"name": "Spending", "values": [sum(spending[m].values()) for m in months]}],
            "kind": "time",
        }
    if as_of := data_date(results):
        cutoff = (date.fromisoformat(as_of) - timedelta(days=90)).isoformat()
        sizes = [t["amount"] for t in txns if t["flow_class"] == "expense" and t["direction"] == "out"
                 and t["date"] > cutoff]
        if sizes:
            datasets["transaction_sizes"] = {
                "kind": "sizes", "values": sizes,
                "description": f"Sizes of spending transactions, last 90 days ({scope} transactions)"}
    for result in results:
        if result.product == "savings" and result.data.get("accounts") and {"goal", "history_start"} <= result.data.keys():
            datasets["goal_projection"] = _goal_history(result.data)
    return datasets


def _goal_history(data: dict) -> dict:
    """Month-end amount saved toward the goal, counted back from today's saved amount by its contributions."""
    goal = data["goal"]
    months, month = [], data["history_start"][:7]
    while month <= data["as_of_date"][:7]:
        months.append(month)
        month = month_after(month)
    contributions = [(t["date"][:7], t["amount"]) for t in data.get("transactions", [])
                     if t["category"] == "goal_contribution" and t["direction"] == "in"]
    history = [goal["current_saved"] - sum(a for m, a in contributions if m > month) for month in months]
    return {"kind": "projection", "keys": months, "history": history, "current": goal["current_saved"],
            "target": goal["target_amount"], "monthly": goal["monthly_contribution"], "name": goal["name"],
            "description": f"{goal['name']}: amount saved each month, projected forward to the target"}


def build_facts(results, datasets: dict[str, dict]) -> dict[str, dict]:
    """Every dollar figure the generated text may mention, keyed for {placeholder} use."""
    facts = {}

    def add(key, label, value, good="none", unit="dollars"):
        facts[key] = {"label": label, "value": value, "good": good, "unit": unit}

    for result in results:
        data = result.data
        if result.product == "other_data" or not data.get("accounts"):
            continue
        owed = result.product in ("credit_card", "loans")
        add(f"{result.product}.balance", f"{_label(result.product)} balance{' owed' if owed else ''}",
            data["balance_total"], "down" if owed else "up")
        if "goal" in data:
            add("savings.goal_target", f"{data['goal']['name']} target", data["goal"]["target_amount"])
            add("savings.goal_saved", f"Saved toward {data['goal']['name']}", data["goal"]["current_saved"], "up")
            add("savings.goal_remaining", f"Left to reach {data['goal']['name']}", data["goal_remaining"], "down")
            add("savings.goal_monthly_contribution", f"Monthly saving toward {data['goal']['name']}",
                data["goal"]["monthly_contribution"], "up")
            add("savings.goal_target_date", f"{data['goal']['name']} target date", data["goal"]["target_date"],
                unit="date")
    # Profile-wide monthly averages: the same in every branch's data, so take the first.
    wellness = next((r.data["wellness_inputs"] for r in results if r.data.get("wellness_inputs")), None)
    if wellness:
        add("monthly.income", "Average monthly income", wellness["monthly_income_avg"], "up")
        add("monthly.spending", "Average monthly spending", wellness["monthly_spending_avg"], "down")
        add("monthly.recurring_bills", "Monthly recurring bills", wellness["monthly_recurring_bills"], "down")
        add("monthly.debt_payments", "Scheduled monthly debt payments",
            wellness["scheduled_monthly_debt_payments"], "down")
        add("liquid_cash", "Cash in checking and savings", wellness["liquid_cash"], "up")
    for key, ds in datasets.items():
        if ds["kind"] == "sizes":
            values = ds["values"]
            add("transaction_sizes.count", "Spending transactions, last 90 days", len(values), unit="count")
            add("transaction_sizes.median", "Median transaction, last 90 days", statistics.median(values))
            add("transaction_sizes.mean", "Average transaction, last 90 days", statistics.mean(values))
            add("transaction_sizes.largest", "Largest transaction, last 90 days", max(values))
        if ds["kind"] not in ("category", "time"):
            continue
        for series in ds["series"]:
            name = series["name"].lower()
            for slug, label, value in zip(ds["keys"], ds["categories"], series["values"]):
                add(f"{key}.{name}.{slug}", f"{series['name']}, {label}", value)
            add(f"{key}.{name}.total", f"{series['name']} total: {ds['description']}", sum(series["values"]))
        if key == "income_vs_spending":
            incomes, spent = (s["values"] for s in ds["series"])
            for month, label, i, s in zip(ds["keys"], ds["categories"], incomes, spent):
                add(f"{key}.net.{month}", f"Income minus spending, {label}", i - s)
    # Per-category monthly average over every month in the history (months with no spend count as $0),
    # so "cut dining in half" needs one fact instead of a six-month sum.
    if months := datasets.get("income_vs_spending", {}).get("keys"):
        totals = defaultdict(int)
        for key, ds in datasets.items():
            if key.startswith("spending_by_category."):
                for slug, value in zip(ds["keys"], ds["series"][0]["values"]):
                    totals[slug] += value
        for slug, total in totals.items():
            add(f"spending.avg_monthly.{slug}", f"Average monthly spending, {_label(slug)}",
                round(total / len(months)), "down")
    return facts


def data_date(results) -> str | None:
    """The records' as-of date (date maths counts from here, not today)."""
    for result in results:
        for data in (result.data, *(v for v in result.data.values() if isinstance(v, dict))):
            if data.get("as_of_date"):
                return data["as_of_date"]
    return None


def money(value: int) -> str:
    return f"-${-value:,}" if value < 0 else f"${value:,}"


def fmt(fact: dict) -> str:
    """A fact's value as display text, by unit."""
    value, unit = fact["value"], fact.get("unit", "dollars")
    if unit == "dollars":
        return money(round(value))
    if unit == "date":
        d = date.fromisoformat(value)
        return f"{d:%B} {d.day}, {d.year}"
    number = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"
    if unit == "percent":
        return f"{number}%"
    if unit in ("days", "months"):
        return f"{number} {unit[:-1] if number == '1' else unit}"
    return number  # count
