"""Environment-driven configuration. Secrets live in .env (gitignored), never in code."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from . import ROOT

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    nessie_api_key: str | None
    nessie_base_url: str
    mongodb_uri: str | None
    mongodb_db: str
    session_secret: str | None = None
    demo_password: str = "waypoint-demo"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")
    profile_cache_ttl: int = 300

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            nessie_api_key=os.getenv("NESSIE_API_KEY") or None,
            nessie_base_url=os.getenv("NESSIE_BASE_URL", "https://prod-api.nessieisreal.com"),
            mongodb_uri=os.getenv("MONGODB_URI") or None,
            mongodb_db=os.getenv("MONGODB_DB", "waypoint"),
            session_secret=os.getenv("WAYPOINT_SESSION_SECRET") or None,
            demo_password=os.getenv("WAYPOINT_DEMO_PASSWORD", "waypoint-demo"),
            cors_origins=tuple(o.strip() for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()),
            profile_cache_ttl=int(os.getenv("PROFILE_CACHE_TTL", "300")),
        )
