"""Low-level Nessie HTTP client: auth, timeouts, retries, throttling, response normalization.

Behavior handled here (verified against the live API in Phase 1):
- The API key goes in the `key` query parameter; it is never logged.
- POST returns {"code", "message", "objectCreated": {..., "_id"}}; `create()` returns objectCreated.
- Some list responses use "id" instead of "_id"; every object is normalized to have "_id".
- Listing transfers on an account with none returns 404 "No transfers found"; lists treat
  404 as empty.
- GETs are retried on timeouts, 429 and 5xx. POSTs are NOT retried automatically, because a
  timed-out POST may have succeeded; the seeder re-checks Nessie by marker before retrying.
"""
import logging
import time
from typing import Any

import httpx

from ...config import Settings

log = logging.getLogger("waypoint.nessie")

RETRY_STATUSES = {429, 500, 502, 503, 504}


class NessieError(Exception):
    def __init__(self, method: str, path: str, status: int | None, detail: Any):
        self.method, self.path, self.status, self.detail = method, path, status, detail
        super().__init__(f"Nessie {method} {path} failed ({status}): {str(detail)[:300]}")


def normalize(obj: Any) -> Any:
    if isinstance(obj, list):
        return [normalize(o) for o in obj]
    if isinstance(obj, dict) and "_id" not in obj and "id" in obj:
        obj = {**obj, "_id": obj["id"]}
    return obj


class NessieClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, *, timeout: float = 30.0,
                 max_retries: int = 4, backoff: float = 1.0, min_interval: float = 0.05,
                 transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        settings = Settings.load()
        self.api_key = api_key or settings.nessie_api_key
        if not self.api_key:
            raise RuntimeError("NESSIE_API_KEY is not set (add it to .env)")
        self.base_url = (base_url or settings.nessie_base_url).rstrip("/")
        self.max_retries, self.backoff, self.min_interval = max_retries, backoff, min_interval
        self._sleep = sleep
        self._last = 0.0
        self.calls = 0
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport,
                                  headers={"Accept": "application/json"})

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- core -----------------------------------------------------------------
    def _throttle(self):
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = time.monotonic()

    def request(self, method: str, path: str, json: dict | None = None, *, retry: bool | None = None) -> tuple[int, Any]:
        retry = method == "GET" if retry is None else retry
        attempts = self.max_retries + 1 if retry else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            self._throttle()
            self.calls += 1
            try:
                resp = self._http.request(method, path, params={"key": self.api_key}, json=json)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = NessieError(method, path, None, f"{type(exc).__name__}: {exc}")
                log.warning("Nessie %s %s transport error (attempt %d): %s", method, path, attempt + 1, exc)
            else:
                body = _parse(resp)
                if resp.status_code < 400:
                    return resp.status_code, normalize(body)
                last_exc = NessieError(method, path, resp.status_code, body)
                if resp.status_code not in RETRY_STATUSES:
                    raise last_exc
                log.warning("Nessie %s %s -> %d (attempt %d)", method, path, resp.status_code, attempt + 1)
            if attempt + 1 < attempts:
                self._sleep(self.backoff * 2 ** attempt)
        raise last_exc  # type: ignore[misc]

    # -- helpers --------------------------------------------------------------
    def get(self, path: str) -> Any:
        return self.request("GET", path)[1]

    def get_or_none(self, path: str) -> Any:
        try:
            return self.get(path)
        except NessieError as exc:
            if exc.status == 404:
                return None
            raise

    def list(self, path: str) -> list[dict]:
        try:
            data = self.get(path)
        except NessieError as exc:
            if exc.status == 404:  # e.g. "No transfers found for this account"
                return []
            raise
        if not isinstance(data, list):
            raise NessieError("GET", path, 200, f"expected a list, got {type(data).__name__}")
        return data

    def create(self, path: str, body: dict) -> dict:
        status, data = self.request("POST", path, json=body)
        created = data.get("objectCreated") if isinstance(data, dict) else None
        if not created or "_id" not in created:
            raise NessieError("POST", path, status, f"no objectCreated._id in response: {data}")
        return normalize(created)

    def delete(self, path: str) -> bool:
        try:
            self.request("DELETE", path, retry=True)  # DELETE is idempotent
            return True
        except NessieError as exc:
            if exc.status == 404:
                return False
            raise


def _parse(resp: httpx.Response) -> Any:
    if not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return resp.text
