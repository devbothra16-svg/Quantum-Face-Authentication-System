"""Redis-backed request throttling and replay nonce storage."""

import time
from collections import defaultdict, deque

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_redis = Redis.from_url(settings.redis_url, socket_connect_timeout=0.15, socket_timeout=0.15)
_requests: dict[str, deque[float]] = defaultdict(deque)
_nonces: set[str] = set()


def allow_request(identity: str, limit: int = 60, window_seconds: int = 60) -> bool:
    """Allow at most limit requests per identity in a rolling window."""
    try:
        key = f"rate:{identity}"
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, window_seconds)
        return count <= limit
    except RedisError:
        now = time.monotonic()
        requests = _requests[identity]
        while requests and requests[0] <= now - window_seconds:
            requests.popleft()
        if len(requests) >= limit:
            return False
        requests.append(now)
        return True


def accept_nonce(nonce: str, ttl_seconds: int = 300) -> bool:
    """Atomically consume a nonce, falling back to local memory if Redis is down."""
    try:
        return bool(_redis.set(f"nonce:{nonce}", "1", nx=True, ex=ttl_seconds))
    except RedisError:
        if nonce in _nonces:
            return False
        _nonces.add(nonce)
        return True
