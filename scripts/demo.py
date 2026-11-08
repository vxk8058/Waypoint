"""Demo CLI: add a goal deposit or a purchase in Nessie, then watch the goal and missions update.

    python scripts/demo.py status
    python scripts/demo.py save 50             # move $50 from checking into the goal's savings account
    python scripts/demo.py spend dining 12     # spend $12 at a merchant you already use in that category

Needs the API running (default http://localhost:8000). Writes go to your Nessie sandbox and are permanent;
`python scripts/seed_nessie.py <profile_id> --reset --yes` clears them. Nessie never changes account
balances for new transactions, so balances stay put while the goal, missions and history move.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from backend.config import Settings  # noqa: E402
from backend.database.mongo import get_database  # noqa: E402
from backend.integrations.nessie.client import NessieClient  # noqa: E402


def login(base: str, email: str) -> httpx.Client:
    api = httpx.Client(base_url=base, timeout=60)
    r = api.post("/auth/login", json={"email": email, "password": Settings.load().demo_password})
    r.raise_for_status()
    api.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return api


def status(api: httpx.Client) -> int:
    """Print the goal and missions from fresh bank data; returns the amount saved."""
    goal = api.get("/api/me/goal", params={"refresh": "true"}).raise_for_status().json()["goal"]
    saved, target = goal["current_saved"], goal["target_amount"]
    pct = 100 * saved / target if target else 0
    bar = "█" * round(pct / 5) + "░" * (20 - round(pct / 5))
    print(f"{goal['name']}: ${saved:,} of ${target:,} ({pct:.1f}%)  {bar}")
    if nxt := next((c for c in (25, 50, 75, 100) if pct < c), None):
        print(f"  next checkpoint {nxt}%: ${max(0, round(target * nxt / 100 - saved)):,} to go")
    for period, m in api.get("/api/me/mission").raise_for_status().json().items():
        name = "This week" if period == "week" else "Today"
        if not m:
            print(f"{name}: no mission yet")
            continue
        verb = "saved" if m["kind"] == "save" else "spent"
        goal_text = f"move ${m['amount']} to {m['label']}" if m["kind"] == "save" else f"keep {m['label']} under ${m['amount']}"
        print(f"{name}: {goal_text} · ${m['progress']} {verb} · {m['status']}")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--email", default="poyo@waypoint.demo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    save = sub.add_parser("save")
    save.add_argument("amount", type=int)
    spend = sub.add_parser("spend")
    spend.add_argument("category")
    spend.add_argument("amount", type=int)
    args = parser.parse_args()
    if args.command != "status" and args.amount <= 0:
        parser.error("amount must be a positive whole number of dollars")

    api = login(args.api, args.email)
    if args.command == "status":
        status(api)
        return

    profile_id = api.get("/auth/me").raise_for_status().json()["profile_id"]
    db = get_database()

    def account(kind: str) -> str:
        doc = db.nessie_id_map.find_one({"profile_id": profile_id, "resource": "account", "local_key": {"$regex": kind}})
        if not doc:
            sys.exit(f"No {kind} account in Nessie for {profile_id}; run scripts/seed_nessie.py first.")
        return doc["nessie_id"]

    today = date.today().isoformat()
    before = status(api)
    with NessieClient() as nessie:
        if args.command == "save":
            # Nessie transfers are one-sided; "(out)"/"(in)" marks each side and "Goal" makes it a goal deposit.
            for kind, side in (("checking", "out"), ("savings", "in")):
                nessie.create(f"/accounts/{account(kind)}/transfers", {
                    "transaction_date": today, "status": "completed", "amount": args.amount,
                    "description": f"Goal contribution ({side})"})
        else:
            sample = api.get("/api/me/transactions", params={"category": args.category, "limit": 1}).json()["items"]
            mapped = sample and db.nessie_id_map.find_one({"resource": "merchant", "local_key": f"merchant:{sample[0]['merchant_key']}"})
            if not mapped:
                sys.exit(f"No merchant you've used for '{args.category}' yet; try dining, coffee, groceries or shopping.")
            nessie.create(f"/accounts/{account('checking')}/purchases", {
                "merchant_id": mapped["nessie_id"], "medium": "balance", "purchase_date": today, "status": "completed",
                "amount": args.amount, "description": f"{sample[0]['merchant_name'] or args.category} (demo)"})
    print(f"\nAdded: {args.command} ${args.amount}. Now:")
    after = status(api)
    if after > before:
        print(f"Goal +${after - before:,}. Reload the dashboard or press ↻ on Missions to see it.")
    else:
        print("Reload the dashboard or press ↻ on Missions to see it.")


if __name__ == "__main__":
    main()
