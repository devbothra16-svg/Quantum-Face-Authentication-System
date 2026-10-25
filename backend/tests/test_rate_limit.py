"""Redis fallback behavior tests."""

from app.core import rate_limit
from redis.exceptions import ConnectionError


class OfflineRedis:
    """Fake Redis client that simulates an unavailable local service."""

    def incr(self, key: str) -> int:
        """Raise a realistic connection error."""
        raise ConnectionError("offline")

    def set(self, *args, **kwargs):
        """Raise a realistic connection error."""
        raise ConnectionError("offline")


def test_rate_limit_and_nonce_fallback(monkeypatch) -> None:
    """Local fallback enforces request ceilings and one-time nonces."""
    monkeypatch.setattr(rate_limit, "_redis", OfflineRedis())
    assert rate_limit.allow_request("test", limit=1)
    assert not rate_limit.allow_request("test", limit=1)
    assert rate_limit.accept_nonce("nonce-test")
    assert not rate_limit.accept_nonce("nonce-test")
