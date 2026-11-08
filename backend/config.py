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

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            nessie_api_key=os.getenv("NESSIE_API_KEY") or None,
            nessie_base_url=os.getenv("NESSIE_BASE_URL", "https://prod-api.nessieisreal.com"),
            mongodb_uri=os.getenv("MONGODB_URI") or None,
            mongodb_db=os.getenv("MONGODB_DB", "waypoint"),
        )
