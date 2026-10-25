"""Enrollment/account API flow tests using an isolated SQLite database."""

import base64

import numpy as np
import pytest
from app.api import routes
from app.core.config import settings
from app.db.models import Base
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def test_enroll_auth_dashboard_revoke_and_erase(monkeypatch, tmp_path) -> None:
    """Exercise consented enrollment, login, history, revocation, and erasure."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    monkeypatch.setattr(routes, "_key", lambda: b"k" * 32)
    monkeypatch.setattr(routes, "check_liveness", lambda frames, challenge: True)
    image = base64.b64encode(b"demo frame").decode()
    monkeypatch.setattr(routes, "get_embedding", lambda frame: np.ones(512, dtype=np.float32))
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path, public_path = tmp_path / "private.pem", tmp_path / "public.pem"
    private_path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    monkeypatch.setattr(settings, "jwt_private_key_path", str(private_path))
    monkeypatch.setattr(settings, "jwt_public_key_path", str(public_path))
    enroll_request = routes.FaceRequest(
        email="person@example.com",
        frames=[image, image],
        nonce="enroll-nonce-0000001",
        challenge="blink",
        consent=True,
    )
    enrolled = routes.enroll(enroll_request, db)
    assert enrolled["status"] == "enrolled"
    auth_request = enroll_request.model_copy(update={"nonce": "auth-nonce-00000000001"})
    authenticated = routes.authenticate(auth_request, db)
    bearer = f"Bearer {authenticated['access_token']}"
    assert routes.me(bearer, db)["history"]
    assert routes.revoke(bearer, db) == {"status": "revoked"}
    assert routes.erase(bearer, db) == {"status": "erased"}
    db.close()
    engine.dispose()


def test_enroll_requires_consent_and_nonce_is_single_use(monkeypatch) -> None:
    """Reject missing consent and re-used request nonces."""
    from unittest.mock import MagicMock

    payload = routes.FaceRequest(
        email="person@example.com",
        frames=["x", "y"],
        nonce="replay-nonce-000001",
        challenge="blink",
        consent=False,
    )
    with pytest.raises(HTTPException) as error:
        routes.enroll(payload, MagicMock())
    assert error.value.status_code == 400
    routes._accept_nonce(payload.nonce)
    with pytest.raises(HTTPException) as replay:
        routes._accept_nonce(payload.nonce)
    assert replay.value.status_code == 409
