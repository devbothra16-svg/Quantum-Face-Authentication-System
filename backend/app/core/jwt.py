"""Short-lived RS256 access tokens."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt


def issue_token(subject: str, private_key_path: str, minutes: int = 5) -> str:
    """Sign a short-lived access JWT with a unique identifier."""
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, Path(private_key_path).read_text(), algorithm="RS256")


def verify_token(token: str, public_key_path: str) -> dict:
    """Validate an RS256 signature and required claims."""
    return jwt.decode(
        token,
        Path(public_key_path).read_text(),
        algorithms=["RS256"],
        options={"require": ["sub", "exp", "iat", "jti"]},
    )
