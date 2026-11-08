"""Badges for verified wins only: computed from the goal, deposits and missions; once earned, kept."""
from datetime import date

from ..schemas.normalized import UnifiedProfile
from . import missions as mission_rules

# (id, label, how to earn it); order is the order students see them.
BADGES = [
    ("goal_25", "Quarter way", "Reach 25% of your goal"),
    ("goal_50", "Halfway", "Reach 50% of your goal"),
    ("goal_75", "Three quarters", "Reach 75% of your goal"),
    ("goal_100", "Goal reached", "Reach your goal"),
    ("saved_100", "First $100", "Save $100 toward your goal"),
    ("saved_500", "$500 saved", "Save $500 toward your goal"),
    ("saved_1000", "$1,000 saved", "Save $1,000 toward your goal"),
    ("saved_2500", "$2,500 saved", "Save $2,500 toward your goal"),
    ("streak_3", "3-month streak", "Deposit to your goal 3 months in a row"),
    ("streak_6", "6-month streak", "Deposit to your goal 6 months in a row"),
    ("mission_1", "First mission", "Complete a mission"),
    ("mission_3", "Mission streak", "Complete 3 missions in a row"),
]


def _longest_month_run(p: UnifiedProfile) -> int:
    months = sorted({(t.date.year, t.date.month) for t in p.transactions
                     if t.category == "goal_contribution" and t.direction == "in"})
    best = run = 0
    for i, (y, m) in enumerate(months):
        run = run + 1 if i and (y * 12 + m) - (months[i - 1][0] * 12 + months[i - 1][1]) == 1 else 1
        best = max(best, run)
    return best


def earned_now(p: UnifiedProfile, mission_docs: list[dict], today: date) -> set[str]:
    pct = 100 * p.goal.current_saved / p.goal.target_amount if p.goal.target_amount else 0
    finished = [mission_rules.progress(m, p, today)["status"] for m in sorted(mission_docs, key=lambda m: m["start"])]
    finished = [s for s in finished if s != "active"]
    tail = 0
    for status in reversed(finished):  # missions met in a row, most recent first
        if status != "met":
            break
        tail += 1
    run = _longest_month_run(p)
    checks = {**{f"goal_{n}": pct >= n for n in (25, 50, 75, 100)},
              **{f"saved_{n}": p.goal.current_saved >= n for n in (100, 500, 1000, 2500)},
              "streak_3": run >= 3, "streak_6": run >= 6, "mission_1": "met" in finished, "mission_3": tail >= 3}
    return {badge for badge, ok in checks.items() if ok}


def badges(db, user_id: str, p: UnifiedProfile, today: date) -> list[dict]:
    """All badges with earned status; newly earned ones are stored so a later withdrawal never takes them away."""
    stored = {b["badge_id"]: b["earned_on"] for b in db.badges.find({"user_id": user_id})}
    for badge in earned_now(p, list(db.missions.find({"user_id": user_id})), today) - stored.keys():
        stored[badge] = today.isoformat()
        db.badges.insert_one({"user_id": user_id, "badge_id": badge, "earned_on": stored[badge]})
    return [{"id": i, "label": label, "hint": hint, "earned": i in stored, "earned_on": stored.get(i)}
            for i, label, hint in BADGES]
