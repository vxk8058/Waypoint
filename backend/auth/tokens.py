"""Stateless signed session tokens: base64url(payload).base64url(HMAC-SHA256)."""
import base64
import hashlib
import hmac
import json
import time


class InvalidToken(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(secret: str, claims: dict, ttl_seconds: int = 12 * 3600, now: float | None = None) -> tuple[str, int]:
    exp = int((now or time.time()) + ttl_seconds)
    payload = _b64(json.dumps({**claims, "exp": exp}, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}", exp


def verify(secret: str, token: str, now: float | None = None) -> dict:
    try:
        payload, sig = token.split(".")
    except ValueError as exc:
        raise InvalidToken("malformed token") from exc
    expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise InvalidToken("bad signature")
    claims = json.loads(_unb64(payload))
    if claims.get("exp", 0) < (now or time.time()):
        raise InvalidToken("token expired")
    return claims
