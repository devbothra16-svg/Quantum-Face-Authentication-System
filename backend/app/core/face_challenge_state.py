"""Short-lived, one-use face-motion challenges stored in Redis."""

import json
import secrets

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
_CHALLENGE_TTL_SECONDS = 120


def issue_face_challenge(email: str) -> tuple[str, int]:
    """Create a random, account-bound challenge with an unpredictable first turn."""
    challenge_id = secrets.token_urlsafe(32)
    first_turn_sign = secrets.choice((-1, 1))
    state = json.dumps({"email": email.casefold(), "first_turn_sign": first_turn_sign})
    try:
        created = _redis.set(
            f"face-challenge:{challenge_id}", state, nx=True, ex=_CHALLENGE_TTL_SECONDS
        )
    except RedisError as exc:
        raise RuntimeError("Face verification is temporarily unavailable") from exc
    if not created:
        raise RuntimeError("Could not start a face verification challenge")
    return challenge_id, first_turn_sign


def consume_face_challenge(challenge_id: str, email: str) -> int:
    """Consume a challenge exactly once and verify it belongs to the submitted account."""
    try:
        raw = _redis.getdel(f"face-challenge:{challenge_id}")
    except RedisError as exc:
        raise RuntimeError("Face verification is temporarily unavailable") from exc
    if raw is None:
        raise ValueError("This face scan expired or was already used. Start a new scan.")
    try:
        state = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("This face scan challenge is invalid. Start a new scan.") from exc
    if state.get("email") != email.casefold():
        raise ValueError("The face scan was started for a different email address.")
    first_turn_sign = state.get("first_turn_sign")
    if first_turn_sign not in (-1, 1):
        raise ValueError("This face scan challenge is invalid. Start a new scan.")
    return int(first_turn_sign)
