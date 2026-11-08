"""Hardcoded demo login, linked to a seeded student profile.

The demo user is stored in MongoDB `users` (password as a PBKDF2 hash) and refreshed at
startup. The password comes from WAYPOINT_DEMO_PASSWORD (default "waypoint-demo").
Every API call derives the profile from the logged-in user, never from the request.
"""
from datetime import datetime, timezone

from pydantic import BaseModel
from pymongo.database import Database

from .passwords import hash_password, verify_password

DEMO_USERS = [
    {"user_id": "user-poyo", "email": "poyo@waypoint.demo", "display_name": "Poyo de Avon",
     "first_name": "Poyo", "last_name": "de Avon", "profile_id": "stu-002"},
]


class PublicUser(BaseModel):
    user_id: str
    email: str
    display_name: str
    first_name: str
    last_name: str
    profile_id: str


def ensure_demo_users(db: Database, password: str) -> None:
    for u in DEMO_USERS:
        existing = db.users.find_one({"user_id": u["user_id"]})
        if existing and verify_password(password, existing.get("password_hash", "")):
            db.users.update_one({"user_id": u["user_id"]}, {"$set": u})
            continue
        db.users.update_one({"user_id": u["user_id"]}, {
            "$set": {**u, "password_hash": hash_password(password), "updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)


def authenticate(db: Database, email: str, password: str) -> PublicUser | None:
    doc = db.users.find_one({"email": email.strip().lower()})
    if not doc or not verify_password(password, doc.get("password_hash", "")):
        return None
    return PublicUser(**{k: doc[k] for k in PublicUser.model_fields})


def get_user(db: Database, user_id: str) -> PublicUser | None:
    doc = db.users.find_one({"user_id": user_id})
    return PublicUser(**{k: doc[k] for k in PublicUser.model_fields}) if doc else None
