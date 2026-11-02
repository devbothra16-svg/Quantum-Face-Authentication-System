"""Enrollment, authentication, account, admin, and health API."""

import os
import uuid
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.face_challenge_state import consume_face_challenge, issue_face_challenge
from app.core.jwt import issue_token, verify_token
from app.core.kms import LocalFileKMS
from app.core.security import cancelable_transform, decrypt_template, encrypt_template
from app.db.models import AuditLog, Template, User
from app.db.session import SessionLocal
from app.services.embedding import get_embedding
from app.services.liveness import liveness_failure_reason
from app.services.matcher import score

router = APIRouter()
FrameData = Annotated[str, StringConstraints(max_length=400_000)]
_GENERIC_FACE_FAILURE = (
    "Verification failed. Check the email and enrolled face, then start a fresh scan."
)


class FaceRequest(BaseModel):
    """Face challenge payload; image bytes remain request-local."""

    email: EmailStr
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    department: str | None = Field(default=None, min_length=1, max_length=120)
    employee_id: str | None = Field(default=None, min_length=1, max_length=80)
    frames: list[FrameData] = Field(min_length=12, max_length=12)
    challenge_id: str = Field(min_length=32, max_length=128)
    consent: bool = False


class FaceChallengeRequest(BaseModel):
    """Account identifier used to bind a short-lived camera challenge."""

    email: EmailStr


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


def _request_embedding(frames: list[str]) -> np.ndarray:
    """Average clear center-pose embeddings, excluding the head-turn samples."""
    if len(frames) != 12:
        raise ValueError("The camera capture was incomplete. Start a new scan.")
    selected = [frames[index] for index in (0, 1, 2, 9, 10, 11)]
    embeddings = []
    for frame in selected:
        try:
            embeddings.append(get_embedding(frame))
        except (ValueError, RuntimeError):
            continue
    if len(embeddings) < 2:
        raise ValueError("Could not get two clear center-face samples. Improve the lighting and try again.")
    mean = np.mean(embeddings, axis=0)
    norm = float(np.linalg.norm(mean))
    if not norm or not np.isfinite(mean).all():
        raise ValueError("Could not build a stable face match. Try again in steady lighting.")
    return mean / norm


def _normalized_email(email: EmailStr) -> str:
    """Normalize account lookup and challenge binding consistently."""
    return str(email).strip().casefold()


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


@router.post("/face/challenge")
def start_face_challenge(payload: FaceChallengeRequest) -> dict:
    """Create a one-use server challenge before capturing camera frames."""
    try:
        challenge_id, first_turn_sign = issue_face_challenge(_normalized_email(payload.email))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "challenge_id": challenge_id,
        "first_turn_sign": first_turn_sign,
        "expires_in_seconds": 120,
    }


@router.post("/enroll")
def enroll(payload: FaceRequest, db: Session = Depends(db_session)) -> dict:
    """Enroll from liveness-checked frames; never persist input frames."""
    if not payload.consent:
        raise HTTPException(400, "Explicit biometric consent is required")
    email = _normalized_email(payload.email)
    full_name = (payload.full_name or "").strip()
    department = (payload.department or "").strip()
    employee_id = (payload.employee_id or "").strip()
    if not full_name or not department or not employee_id:
        raise HTTPException(422, "Name, department, and employee ID are required")
    try:
        first_turn_sign = consume_face_challenge(payload.challenge_id, email)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    liveness_error = liveness_failure_reason(payload.frames, first_turn_sign)
    if liveness_error:
        raise HTTPException(400, liveness_error)
    try:
        embedding = _request_embedding(payload.frames)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None and db.get(Template, user.id) is not None:
        raise HTTPException(409, "This account already has a registered face")
    if user is None:
        user = User(id=str(uuid.uuid4()), email=email)
        db.add(user)
    user.full_name = full_name
    user.department = department
    user.employee_id = employee_id
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
    return {
        "user_id": user.id,
        "status": "enrolled",
        "access_token": issue_token(
            user.id, settings.jwt_private_key_path, settings.access_token_minutes
        ),
        "token_type": "bearer",
    }


@router.post("/auth")
def authenticate(payload: FaceRequest, db: Session = Depends(db_session)) -> dict:
    """Authenticate, audit, and issue a short-lived token."""
    email = _normalized_email(payload.email)
    try:
        first_turn_sign = consume_face_challenge(payload.challenge_id, email)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    liveness_error = liveness_failure_reason(payload.frames, first_turn_sign)
    if liveness_error:
        raise HTTPException(401, liveness_error)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    template = db.get(Template, user.id) if user else None
    if user is None or template is None:
        raise HTTPException(401, _GENERIC_FACE_FAILURE)
    try:
        embedding = _request_embedding(payload.frames)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            401,
            _GENERIC_FACE_FAILURE,
        ) from exc
    transform_secret = decrypt_template(template.transform_secret, _key())
    protected = cancelable_transform(embedding, transform_secret)
    stored = np.frombuffer(decrypt_template(template.ciphertext, _key()), dtype=np.float32)
    similarity = score(protected, stored)
    outcome = "success" if similarity >= settings.face_match_threshold else "failure"
    db.add(AuditLog(user_id=user.id, event="authenticate", outcome=outcome))
    db.commit()
    if outcome == "failure":
        raise HTTPException(
            401,
            _GENERIC_FACE_FAILURE,
        )
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


@router.get("/vault")
def protected_vault(authorization: str = Header(...)) -> dict:
    """Return clearly fictional sample records only to a valid signed-in session."""
    user_id = _subject(authorization)
    return {
        "owner": user_id,
        "records": [
            {
                "id": "sample-001",
                "classification": "CONFIDENTIAL · SAMPLE",
                "title": "Quarterly access review",
                "summary": "Demo record showing how a protected workspace can be gated.",
            },
            {
                "id": "sample-002",
                "classification": "INTERNAL · SAMPLE",
                "title": "Incident response runbook",
                "summary": "Fictional content for demonstrating authenticated access only.",
            },
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
