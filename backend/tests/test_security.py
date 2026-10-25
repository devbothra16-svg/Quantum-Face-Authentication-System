"""Security primitive tests."""

import numpy as np
import pytest
from app.core.security import cancelable_transform, decrypt_template, encrypt_template
from cryptography.exceptions import InvalidTag


def test_aes_gcm_round_trip_and_wrong_key() -> None:
    """Round trip authenticates and rejects a wrong key."""
    key = bytes(range(32))
    encrypted = encrypt_template(b"protected-vector", key)
    assert decrypt_template(encrypted, key) == b"protected-vector"
    with pytest.raises(InvalidTag):
        decrypt_template(encrypted, bytes(reversed(range(32))))


def test_cancelable_transform_revocation_changes_representation() -> None:
    """Different per-user secrets produce distinct templates."""
    embedding = np.arange(512, dtype=np.float32)
    first = cancelable_transform(embedding, b"a" * 32)
    second = cancelable_transform(embedding, b"b" * 32)
    assert first.shape == (128,)
    assert not np.allclose(first, second)


def test_aes_rejects_invalid_key_length() -> None:
    """AES-256 rejects keys of the wrong size."""
    with pytest.raises(ValueError):
        encrypt_template(b"x", b"short")
