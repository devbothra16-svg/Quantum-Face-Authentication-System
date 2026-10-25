"""Enrollment, authentication, account, admin, and health API."""

import os
import uuid

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jwt import issue_token, verify_token
from app.core.kms import LocalFileKMS
from app.core.rate_limit import accept_nonce
from app.core.security import cancelable_transform, decrypt_template, encrypt_template
from app.db.models import AuditLog, Template, User
from app.db.session import SessionLocal
from app.services.embedding import get_embedding
from app.services.liveness import check_liveness
from app.services.matcher import score

router = APIRouter()


class FaceRequest(BaseModel):
    """Face challenge payload; image bytes remain request-local."""

    email: EmailStr
    frames: list[str] = Field(min_length=1, max_length=10)
    nonce: str = Field(min_length=16, max_length=128)
    challenge: str = Field(min_length=1, max_length=64)
    consent: bool = False


def db_session():
    """Yield a request-scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _key() -> bytes:
    """Resolve the local KMS Fernet representation to a 32-byte AES key."""
    return __import__("base64").urlsafe_b64decode(
        LocalFileKMS(settings.kms_key_path).get_data_key()
    )


def _accept_nonce(nonce: str) -> None:
    """Reject nonce reuse; deployments should use Redis SET NX with TTL."""
    if not accept_nonce(nonce):
        raise HTTPException(409, "Challenge nonce already used")


def _subject(authorization: str) -> str:
    """Resolve a bearer token to its subject."""
    try:
        token = authorization.removeprefix("Bearer ")
        return str(verify_token(token, settings.jwt_public_key_path)["sub"])
    except Exception as exc:
        raise HTTPException(401, "Invalid token") from exc


@router.get("/health")
def health() -> dict:
    """Health endpoint."""
    return {"status": "ok", "quantum": settings.use_quantum}


@router.post("/enroll")
def enroll(payload: FaceRequest, db: Session = Depends(db_session)) -> dict:
    """Enroll from liveness-checked frames; never persist input frames."""
    if not payload.consent:
        raise HTTPException(400, "Explicit biometric consent is required")
    _accept_nonce(payload.nonce)
    if not check_liveness(payload.frames, payload.challenge):
        raise HTTPException(400, "Liveness check failed")
    embedding = np.mean([get_embedding(frame) for frame in payload.frames], axis=0)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        user = User(id=str(uuid.uuid4()), email=str(payload.email))
        db.add(user)
    db.flush()
    transform_secret = os.urandom(32)
    protected = cancelable_transform(embedding, transform_secret)
    db.merge(
        Template(
            user_id=user.id,
            ciphertext=encrypt_template(protected.tobytes(), _key()),
            transform_secret=encrypt_template(transform_secret, _key()),
        )
    )
    db.add(AuditLog(user_id=user.id, event="enroll", outcome="success"))
    db.commit()
    return {"user_id": user.id, "status": "enrolled"}


@router.post("/auth")
def authenticate(payload: FaceRequest, db: Session = Depends(db_session)) -> dict:
    """Authenticate, audit, and issue a short-lived token."""
    _accept_nonce(payload.nonce)
    if not check_liveness(payload.frames, payload.challenge):
        raise HTTPException(401, "Liveness check failed")
    user = db.scalar(select(User).where(User.email == payload.email))
    template = db.get(Template, user.id) if user else None
    if user is None or template is None:
        raise HTTPException(401, "Authentication failed")
    embedding = np.mean([get_embedding(frame) for frame in payload.frames], axis=0)
    transform_secret = decrypt_template(template.transform_secret, _key())
    protected = cancelable_transform(embedding, transform_secret)
    stored = np.frombuffer(decrypt_template(template.ciphertext, _key()), dtype=np.float32)
    similarity = score(protected, stored)
    outcome = "success" if similarity >= 0.72 else "failure"
    db.add(AuditLog(user_id=user.id, event="authenticate", outcome=outcome))
    db.commit()
    if outcome == "failure":
        raise HTTPException(401, "Authentication failed")
    return {
        "access_token": issue_token(
            user.id, settings.jwt_private_key_path, settings.access_token_minutes
        ),
        "token_type": "bearer",
        "similarity": similarity,
    }


@router.get("/users/me")
def me(authorization: str = Header(...), db: Session = Depends(db_session)) -> dict:
    """Return authenticated user's recent audit history."""
    subject = _subject(authorization)
    rows = db.scalars(
        select(AuditLog).where(AuditLog.user_id == subject).order_by(AuditLog.id.desc()).limit(50)
    ).all()
    return {
        "user_id": subject,
        "history": [
            {
                "event": r.event,
                "outcome": r.outcome,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.delete("/users/me")
def erase(authorization: str = Header(...), db: Session = Depends(db_session)) -> dict:
    """Erase template, audit history, and account."""
    subject = _subject(authorization)
    db.query(Template).filter_by(user_id=subject).delete()
    db.query(AuditLog).filter_by(user_id=subject).delete()
    db.query(User).filter_by(id=subject).delete()
    db.commit()
    return {"status": "erased"}


@router.post("/users/me/revoke")
def revoke(authorization: str = Header(...), db: Session = Depends(db_session)) -> dict:
    """Revoke template; a later enrollment generates a fresh transform secret."""
    subject = _subject(authorization)
    db.query(Template).filter_by(user_id=subject).delete()
    db.add(AuditLog(user_id=subject, event="template_revoke", outcome="success"))
    db.commit()
    return {"status": "revoked"}
