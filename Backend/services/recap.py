"""Weekly "Wrapped" recap, built entirely in code from transactions (no AI): every number is from the records."""
from collections import defaultdict
from datetime import date, timedelta

from ..agent.ui.components import validate_document
from ..schemas.normalized import UnifiedProfile
from . import missions as mission_rules

MONEY = {"style": "currency", "decimals": 0}


def window(p: UnifiedProfile, mode: str, today: date) -> tuple[date, date]:
    """Inclusive (start, end). Ends at the latest data date so seeded profiles still have a week to show."""
    ref = min(today, p.as_of_date)
    end = ref if mode == "last7" else ref - timedelta(days=(ref.weekday() + 1) % 7)  # last full Mon–Sun week
    return end - timedelta(days=6), end


def _signed(t) -> int:
    return t.amount if t.direction == "out" else -t.amount


def recap(p: UnifiedProfile, mission_docs: list[dict], badge_list: list[dict], mode: str, today: date) -> dict:
    start, end = window(p, mode, today)
    week = [t for t in p.transactions if start <= t.date <= end]
    by_category, by_merchant = defaultdict(int), defaultdict(int)
    for t in week:
        if t.flow_class == "expense":
            by_category[t.category.replace("_", " ").capitalize()] += _signed(t)
            by_merchant[t.merchant_name or t.description] += _signed(t)
    spent = sum(by_category.values())
    history = [t for t in p.transactions if t.flow_class == "expense"]
    usual = round(sum(map(_signed, history)) * 7 / ((p.as_of_date - p.history_start).days + 1))
    saved = sum(t.amount for t in week if t.category == "goal_contribution" and t.direction == "in")
    days_closer = round(saved / p.goal.monthly_contribution * 30) if p.goal.monthly_contribution else 0
    ended = [mission_rules.progress(m, p, today) for m in mission_docs if start.isoformat() < m["end"] <= (end + timedelta(days=1)).isoformat()]
    met = sum(m["status"] == "met" for m in ended)
    new_badges = [b["label"] for b in badge_list if b["earned_on"] and start.isoformat() <= b["earned_on"] <= end.isoformat()]

    span = f"{start:%b} {start.day} – {end:%b} {end.day}"
    diff = spent - usual
    lead = (f"You spent **${spent:,}** this week, **${abs(diff):,} {'less' if diff <= 0 else 'more'}** than a usual week."
            if usual else f"You spent **${spent:,}** this week.")
    wins = [f"Biggest spot: **{max(by_merchant, key=by_merchant.get)}**"] if by_merchant else []
    if saved:
        wins.append(f"Moved **${saved:,}** to {p.goal.name}, about **{days_closer} days** closer")
    if ended:
        wins.append(f"Missions: **{met} of {len(ended)}** completed")
    wins += [f"New badge: **{label}**" for label in new_badges]
    blocks = [
        {"type": "heading", "props": {"text": f"Your week: {span}", "level": 1}},
        {"type": "paragraph", "props": {"text": lead, "size": "lead"}},
        {"type": "stats", "props": {"items": [
            {"label": "Spent", "value": spent, "format": MONEY, "goodDirection": "down", "caption": "vs. a usual week",
             **({"change": round((spent - usual) / usual * 100, 1)} if usual else {})},
            {"label": f"Saved toward {p.goal.name}", "value": saved, "format": MONEY, "goodDirection": "up"},
            {"label": "Days closer to your goal", "value": f"{days_closer} days", "goodDirection": "up"},
        ]}},
    ]
    if by_category:
        items = sorted(((c, v) for c, v in by_category.items() if v > 0), key=lambda cv: -cv[1])
        blocks.append({"type": "bar_chart", "props": {
            "title": "Where your money went", "orientation": "horizontal", "valueLabels": "all", "valueFormat": MONEY,
            "categories": [c for c, _ in items], "series": [{"name": "Spent", "values": [v for _, v in items]}]}})
    if wins:
        blocks.append({"type": "list", "props": {"items": wins}})
    blocks.append({"type": "paragraph", "props": {"text": "Every number comes straight from your transactions.",
                                                  "size": "small", "tone": "muted"}})
    return validate_document({"blocks": blocks})
