"""Planner-requested data queries over fetched transactions: the model picks filters, code filters and counts."""
import statistics
from collections import defaultdict


def _matches(t: dict, q: dict) -> bool:
    text = f"{t.get('merchant_name') or ''} {t.get('description') or ''}".lower()
    return ((not q["merchant"] or q["merchant"].lower() in text)
            and (not q["category"] or t["category"] == q["category"])
            and (not q["account_type"] or t["account_type"] == q["account_type"])
            and (not q["direction"] or t["direction"] == q["direction"])
            and (not q["flow_class"] or t["flow_class"] == q["flow_class"])
            and (not q["date_from"] or t["date"] >= q["date_from"])
            and (not q["date_to"] or t["date"] <= q["date_to"]))


def _group(t: dict, by: str) -> str:
    if by == "month":
        return t["date"][:7]
    if by == "category":
        return t["category"].replace("_", " ").capitalize()
    return t.get("merchant_name") or t.get("description") or "Unknown"


def describe(q: dict) -> str:
    filters = [f"{k.replace('_', ' ')} {v}" for k, v in q.items()
               if k not in ("name", "label", "aggregate", "group_by") and v]
    return f"{q['aggregate']} of transactions" + (f" where {', '.join(filters)}" if filters else "")


def run_query(q: dict, transactions: list[dict]) -> dict:
    """One result like a calculation's: name, label, unit, value or error; "top" also returns items."""
    rows = [t for t in transactions if _matches(t, q)]
    amounts = [t["amount"] for t in rows]
    out = {"name": q["name"], "label": q["label"], "unit": "count" if q["aggregate"] == "count" else "dollars",
           "formula": describe(q), "query": True}
    if q["aggregate"] == "count":
        out["value"] = len(rows)
    elif q["aggregate"] == "sum":
        out["value"] = sum(amounts)
    elif not rows:
        out["error"] = "No matching transactions"
    elif q["aggregate"] == "top":
        groups = defaultdict(int)
        for t in rows:
            groups[_group(t, q["group_by"] or "merchant")] += t["amount"]
        out["items"] = sorted(groups.items(), key=lambda kv: -kv[1])[:5]
        out["value"] = out["items"][0][1]
    else:
        out["value"] = {"average": statistics.mean, "min": min, "max": max}[q["aggregate"]](amounts)
    return out
