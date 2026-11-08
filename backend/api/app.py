"""Waypoint FastAPI application (Phase 4: auth + Nessie-backed retrieval endpoints).

Run:  uvicorn backend.api.main:app --reload
Docs: http://localhost:8000/docs
"""
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from pymongo.database import Database

from ..agent.graph import build_agent_graph, run_agent
from ..agent.state import initial_state
from ..auth import tokens
from ..auth.users import PublicUser, authenticate, ensure_demo_users, get_user
from ..config import Settings
from ..schemas.normalized import (
    MonthlySummary, UnifiedAccount, UnifiedBill, UnifiedGoal, UnifiedProfile, UnifiedTransaction, WellnessInputs,
)
from ..services import badges, missions, recap
from ..services.profile_service import ProfileNotFound, ProfileService

log = logging.getLogger("waypoint.api")
bearer = HTTPBearer(auto_error=False)


# -- response models --------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # no profile_id: the agent always uses the signed-in user's profile

    question: str = Field(min_length=1, max_length=1000)


class MissionRequest(BaseModel):
    hint: str = Field(default="", max_length=300)  # e.g. a Simulation question; data for the picker, never instructions


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: PublicUser


class DataInfo(BaseModel):
    profile_id: str
    data_mode: str
    stale: bool
    as_of_date: date
    fetched_at: str | None
    warnings: list[str]


class AccountsResponse(BaseModel):
    data: DataInfo
    accounts: list[UnifiedAccount]


class TransactionsResponse(BaseModel):
    data: DataInfo
    items: list[UnifiedTransaction]
    total: int
    limit: int
    offset: int


class BillsResponse(BaseModel):
    data: DataInfo
    bills: list[UnifiedBill]
    monthly_total: int


class GoalResponse(BaseModel):
    data: DataInfo
    goal: UnifiedGoal


class SummaryResponse(BaseModel):
    data: DataInfo
    monthly_summary: list[MonthlySummary]
    wellness_inputs: WellnessInputs


def data_info(p: UnifiedProfile) -> DataInfo:
    return DataInfo(profile_id=p.profile_id, data_mode=p.data_mode, stale=bool(p.metadata.get("stale")),
                    as_of_date=p.as_of_date, fetched_at=p.metadata.get("fetched_at"),
                    warnings=p.metadata.get("warnings", []))


# -- app factory ------------------------------------------------------------------
def create_app(db: Database | None = None, profiles: ProfileService | None = None,
               settings: Settings | None = None, agent=None) -> FastAPI:
    settings = settings or Settings.load()
    secret = settings.session_secret or secrets.token_hex(32)
    if not settings.session_secret:
        log.warning("WAYPOINT_SESSION_SECRET not set: using a random secret (sessions reset on restart)")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal db, profiles
        if db is None:
            from ..database.mongo import ensure_indexes, get_database
            db = get_database()
            ensure_indexes(db)
        if profiles is None:
            gateway = None
            if settings.nessie_api_key:
                from ..integrations.nessie.client import NessieClient
                from ..integrations.nessie.gateway import NessieGateway
                gateway = NessieGateway(NessieClient())
            profiles = ProfileService(db, gateway, ttl_seconds=settings.profile_cache_ttl)
        ensure_demo_users(db, settings.demo_password)
        app.state.db, app.state.profiles = db, profiles
        app.state.agent = agent or build_agent_graph(profiles)  # models load lazily on first question
        yield

    app = FastAPI(title="Waypoint API", version="0.4.0", lifespan=lifespan,
                  description="Student financial profile backed by Capital One Nessie and PNC wellness data.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    def current_user(request: Request,
                     creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> PublicUser:
        if creds is None:
            raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
        try:
            claims = tokens.verify(secret, creds.credentials)
        except tokens.InvalidToken as exc:
            raise HTTPException(401, f"Invalid session: {exc}", headers={"WWW-Authenticate": "Bearer"}) from None
        user = get_user(request.app.state.db, claims["sub"])
        if user is None:
            raise HTTPException(401, "User no longer exists")
        return user

    def current_profile(request: Request, user: Annotated[PublicUser, Depends(current_user)],
                        refresh: bool = Query(False, description="bypass the cache and refetch from Nessie")
                        ) -> UnifiedProfile:
        try:
            return request.app.state.profiles.get(user.profile_id, refresh=refresh)
        except ProfileNotFound:
            raise HTTPException(404, f"Profile {user.profile_id} not found; run the Phase 2 pipeline with "
                                     "--save-mongo") from None

    Profile = Annotated[UnifiedProfile, Depends(current_profile)]

    @app.get("/health", tags=["system"])
    def health(request: Request):
        try:
            request.app.state.db.client.admin.command("ping")
            mongo = "ok"
        except Exception as exc:  # noqa: BLE001
            mongo = f"error: {type(exc).__name__}"
        return {"status": "ok" if mongo == "ok" else "degraded", "mongo": mongo,
                "nessie_configured": bool(settings.nessie_api_key), "time": datetime.now(timezone.utc)}

    @app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
    def login(body: LoginRequest, request: Request):
        user = authenticate(request.app.state.db, body.email, body.password)
        if user is None:
            raise HTTPException(401, "Invalid email or password")
        token, exp = tokens.issue(secret, {"sub": user.user_id, "profile_id": user.profile_id})
        return LoginResponse(access_token=token, expires_at=datetime.fromtimestamp(exp, timezone.utc), user=user)

    @app.get("/auth/me", response_model=PublicUser, tags=["auth"])
    def me(user: Annotated[PublicUser, Depends(current_user)]):
        return user

    @app.get("/api/me/profile", response_model=UnifiedProfile, tags=["profile"])
    def profile(p: Profile):
        """Full unified profile: user, accounts, transactions, bills, goal, summary, metadata."""
        return p

    @app.get("/api/me/accounts", response_model=AccountsResponse, tags=["profile"])
    def accounts(p: Profile):
        return AccountsResponse(data=data_info(p), accounts=p.accounts)

    @app.get("/api/me/transactions", response_model=TransactionsResponse, tags=["profile"])
    def transactions(p: Profile, account_id: str | None = None, start_date: date | None = None,
                     end_date: date | None = None, flow_class: str | None = None, category: str | None = None,
                     limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        """Newest first. Filters: account_id, date range (inclusive), flow_class, category."""
        if start_date and end_date and start_date > end_date:
            raise HTTPException(422, "start_date must not be after end_date")
        if account_id and account_id not in {a.account_id for a in p.accounts}:
            raise HTTPException(404, "Unknown account for this user")
        rows = [t for t in p.transactions
                if (not account_id or t.account_id == account_id)
                and (not start_date or t.date >= start_date) and (not end_date or t.date <= end_date)
                and (not flow_class or t.flow_class == flow_class) and (not category or t.category == category)]
        rows.sort(key=lambda t: (t.date, t.transaction_id), reverse=True)
        return TransactionsResponse(data=data_info(p), items=rows[offset:offset + limit], total=len(rows),
                                    limit=limit, offset=offset)

    @app.get("/api/me/bills", response_model=BillsResponse, tags=["profile"])
    def bills(p: Profile):
        """Recurring obligations, soonest due first (due dates computed by Nessie)."""
        active = [b for b in p.bills if b.status in ("recurring", "pending")]
        return BillsResponse(data=data_info(p), bills=sorted(p.bills, key=lambda b: b.next_due_date),
                             monthly_total=sum(b.amount for b in active))

    @app.get("/api/me/goal", response_model=GoalResponse, tags=["profile"])
    def goal(p: Profile):
        return GoalResponse(data=data_info(p), goal=p.goal)

    @app.get("/api/me/summary", response_model=SummaryResponse, tags=["profile"])
    def summary(p: Profile):
        """Monthly income/spending/debt summary and raw inputs for the wellness engine."""
        return SummaryResponse(data=data_info(p), monthly_summary=p.monthly_summary,
                               wellness_inputs=p.wellness_inputs)

    def latest_mission(db, user_id: str, period: str) -> dict | None:
        legacy = [{"period": {"$exists": False}}] if period == "week" else []  # early weekly missions had no period
        return db.missions.find_one({"user_id": user_id, "$or": [{"period": period}, *legacy]}, sort=[("start", -1)])

    @app.get("/api/me/mission", tags=["missions"])
    def mission(p: Profile, request: Request, user: Annotated[PublicUser, Depends(current_user)]):
        """The latest weekly mission and daily challenge, with progress measured from transactions."""
        today = date.today()
        return {period: missions.progress(doc, p, today) if (doc := latest_mission(request.app.state.db, user.user_id, period))
                else None for period in ("week", "day")}

    @app.post("/api/me/mission", tags=["missions"])
    def start_mission(p: Profile, request: Request, user: Annotated[PublicUser, Depends(current_user)],
                      period: Literal["week", "day"] = Query("week"), body: MissionRequest | None = None):
        """An AI picks the mission from the customer's data; the server checks it and sets every number."""
        db, today = request.app.state.db, date.today()
        latest = latest_mission(db, user.user_id, period)
        if latest and missions.progress(latest, p, today)["status"] == "active":
            raise HTTPException(409, "A mission for this period is already in progress")
        if (doc := missions.generate(p, period, user.user_id, today, hint=body.hint if body else "")) is None:
            raise HTTPException(422, "Not enough spending history to set a mission")
        db.missions.insert_one(dict(doc))  # insert_one adds _id to the dict it gets
        return {"mission": missions.progress(doc, p, today)}

    @app.get("/api/me/badges", tags=["missions"])
    def get_badges(p: Profile, request: Request, user: Annotated[PublicUser, Depends(current_user)]):
        """Badges for verified wins; earned ones are stored so they are never taken away."""
        return badges.badges(request.app.state.db, user.user_id, p, date.today())

    @app.get("/api/me/recap", tags=["missions"])
    def get_recap(p: Profile, request: Request, user: Annotated[PublicUser, Depends(current_user)],
                  mode: Literal["last7", "calendar"] = Query("last7")):
        """A code-built weekly recap document (same block format as Simulation answers)."""
        db, today = request.app.state.db, date.today()
        return recap.recap(p, list(db.missions.find({"user_id": user.user_id})),
                           badges.badges(db, user.user_id, p, today), mode, today)

    @app.post("/api/me/agent", tags=["agent"])
    def ask_agent(body: AgentRequest, request: Request, user: Annotated[PublicUser, Depends(current_user)]) -> dict:
        """Read-only banking assistant; returns an AI document (`{"blocks": [...]}`) for the frontend renderer."""
        try:
            state = initial_state(body.question, user)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return run_agent(request.app.state.agent, state)["final_ui"]

    return app
