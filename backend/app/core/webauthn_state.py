"""Short-lived, single-use WebAuthn challenge storage in Redis."""

import json
import secrets

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
_CHALLENGE_TTL_SECONDS = 300


def store_challenge(purpose: str, user_id: str, challenge: str) -> str:
    """Persist a ceremony challenge and bind it to one user and one purpose."""
    ceremony_id = secrets.token_urlsafe(32)
    value = json.dumps({"purpose": purpose, "user_id": user_id, "challenge": challenge})
    try:
        created = _redis.set(
            f"webauthn:{ceremony_id}", value, nx=True, ex=_CHALLENGE_TTL_SECONDS
        )
    except RedisError as exc:
        raise RuntimeError("Passkey service is temporarily unavailable") from exc
    if not created:
        raise RuntimeError("Could not create a passkey ceremony")
    return ceremony_id


def consume_challenge(ceremony_id: str, purpose: str, user_id: str) -> bytes:
    """Consume a ceremony once, checking its purpose and account binding."""
    try:
        raw = _redis.getdel(f"webauthn:{ceremony_id}")
    except RedisError as exc:
        raise RuntimeError("Passkey service is temporarily unavailable") from exc
    if raw is None:
        raise ValueError("Passkey challenge expired or already used")
    try:
        state = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Passkey challenge is invalid") from exc
    if state.get("purpose") != purpose or state.get("user_id") != user_id:
        raise ValueError("Passkey challenge does not match this operation")
    try:
        encoded = state["challenge"]
        return __import__("webauthn").base64url_to_bytes(encoded)
    except (KeyError, ValueError) as exc:
        raise ValueError("Passkey challenge is invalid") from exc
