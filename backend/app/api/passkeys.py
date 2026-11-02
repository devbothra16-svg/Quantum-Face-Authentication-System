"""Windows Hello and passkey registration and authentication routes."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.routes import _subject, db_session
from app.core.config import settings
from app.core.jwt import issue_token
from app.core.webauthn_state import consume_challenge, store_challenge
from app.db.models import AuditLog, Passkey, User

router = APIRouter(prefix="/passkeys")


class PasskeyOptionsRequest(BaseModel):
    """Account identifier used to find existing passkeys."""

    email: EmailStr


class PasskeyVerifyRequest(BaseModel):
    """Browser response to a registration or authentication ceremony."""

    ceremony_id: str = Field(min_length=32, max_length=128)
    credential: dict[str, Any]


def _credential_id(credential: dict[str, Any]) -> bytes:
    """Decode the browser's credential identifier."""
    encoded = credential.get("rawId") or credential.get("id")
    if not isinstance(encoded, str):
        raise ValueError("Passkey credential is invalid")
    try:
        return base64url_to_bytes(encoded)
    except ValueError as exc:
        raise ValueError("Passkey credential is invalid") from exc


def _challenge(purpose: str, user_id: str, challenge: bytes) -> str:
    """Store challenge state and convert expected validation failures to HTTP errors."""
    import base64

    encoded = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode("ascii")
    try:
        return store_challenge(purpose, user_id, encoded)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


def _expected_challenge(ceremony_id: str, purpose: str, user_id: str) -> bytes:
    """Consume the single-use challenge for this account and ceremony."""
    try:
        return consume_challenge(ceremony_id, purpose, user_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/register/options")
def registration_options(
    authorization: str = Header(...), db: Session = Depends(db_session)
) -> dict:
    """Prepare a passkey enrollment for an already authenticated account."""
    user_id = _subject(authorization)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Authentication required")
    existing = db.scalars(select(Passkey).where(Passkey.user_id == user.id)).all()
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=uuid.UUID(user.id).bytes,
        user_name=user.email,
        user_display_name=user.email,
        timeout=60_000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=item.credential_id) for item in existing
        ],
    )
    ceremony_id = _challenge("register", user.id, options.challenge)
    return {"ceremony_id": ceremony_id, "options": json.loads(options_to_json(options))}


@router.post("/register/verify")
def registration_verify(
    payload: PasskeyVerifyRequest,
    authorization: str = Header(...),
    db: Session = Depends(db_session),
) -> dict:
    """Verify and persist only the passkey public key and signature counter."""
    user_id = _subject(authorization)
    challenge = _expected_challenge(payload.ceremony_id, "register", user_id)
    try:
        result = verify_registration_response(
            credential=payload.credential,
            expected_challenge=challenge,
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(400, "Passkey registration could not be verified") from exc
    if db.get(Passkey, result.credential_id) is not None:
        raise HTTPException(409, "This passkey is already registered")
    db.add(
        Passkey(
            credential_id=result.credential_id,
            user_id=user_id,
            public_key=result.credential_public_key,
            sign_count=result.sign_count,
        )
    )
    db.add(AuditLog(user_id=user_id, event="passkey_register", outcome="success"))
    db.commit()
    return {"status": "passkey_registered"}


@router.post("/auth/options")
def authentication_options(
    payload: PasskeyOptionsRequest, db: Session = Depends(db_session)
) -> dict:
    """Prepare a passkey sign-in without requesting webcam access."""
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    passkeys = db.scalars(select(Passkey).where(Passkey.user_id == user.id)).all() if user else []
    if user is None or not passkeys:
        raise HTTPException(401, "No passkey is registered for this account")
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        timeout=60_000,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=item.credential_id) for item in passkeys
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    ceremony_id = _challenge("authenticate", user.id, options.challenge)
    return {"ceremony_id": ceremony_id, "options": json.loads(options_to_json(options))}


@router.post("/auth/verify")
def authentication_verify(
    payload: PasskeyVerifyRequest, db: Session = Depends(db_session)
) -> dict:
    """Verify a signed passkey assertion and issue the app's normal session token."""
    try:
        credential_id = _credential_id(payload.credential)
    except ValueError as exc:
        raise HTTPException(401, "Passkey authentication failed") from exc
    passkey = db.get(Passkey, credential_id)
    user = db.get(User, passkey.user_id) if passkey else None
    if passkey is None or user is None:
        raise HTTPException(401, "Passkey authentication failed")
    challenge = _expected_challenge(payload.ceremony_id, "authenticate", user.id)
    try:
        result = verify_authentication_response(
            credential=payload.credential,
            expected_challenge=challenge,
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        db.add(AuditLog(user_id=user.id, event="passkey_authenticate", outcome="failure"))
        db.commit()
        raise HTTPException(401, "Passkey authentication failed") from exc
    passkey.sign_count = result.new_sign_count
    db.add(AuditLog(user_id=user.id, event="passkey_authenticate", outcome="success"))
    db.commit()
    return {
        "access_token": issue_token(
            user.id, settings.jwt_private_key_path, settings.access_token_minutes
        ),
        "token_type": "bearer",
    }
