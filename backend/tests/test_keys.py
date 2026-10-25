"""Key manager and token tests."""

from pathlib import Path

import jwt
import pytest
from app.core.jwt import issue_token, verify_token
from app.core.kms import AWSKMSAdapter, LocalFileKMS
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def test_local_kms_generates_stable_development_key(tmp_path: Path) -> None:
    """Local key appears once and stays stable."""
    kms = LocalFileKMS(str(tmp_path / "key"))
    assert kms.get_data_key() == kms.get_data_key()


def test_aws_adapter_requires_real_configuration() -> None:
    """Cloud boundary fails closed until integrated."""
    with pytest.raises(NotImplementedError):
        AWSKMSAdapter("key-id").get_data_key()


def test_rs256_token_round_trip(tmp_path: Path) -> None:
    """Tokens are signed and verified with generated RSA keys."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
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
    token = issue_token("user-1", str(private_path))
    assert verify_token(token, str(public_path))["sub"] == "user-1"
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_path = tmp_path / "wrong.pem"
    wrong_path.write_bytes(
        other.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    with pytest.raises(jwt.InvalidTokenError):
        verify_token(token, str(wrong_path))
