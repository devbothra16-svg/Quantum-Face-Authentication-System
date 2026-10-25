"""Encryption and cancelable transforms for biometric templates."""

import hashlib
import hmac
import os

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def cancelable_transform(embedding: np.ndarray, secret: bytes, output_dim: int = 128) -> np.ndarray:
    """Apply a user-specific seeded orthogonal projection to a vector."""
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    seed = int.from_bytes(hmac.new(secret, b"projection", hashlib.sha256).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(vector.size, output_dim)).astype(np.float32)
    q, _ = np.linalg.qr(matrix, mode="reduced")
    transformed = vector @ q
    norm = np.linalg.norm(transformed)
    return transformed / norm if norm else transformed


def encrypt_template(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt bytes with AES-256-GCM and prepend a fresh nonce."""
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires exactly 32 key bytes")
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, b"face-template:v1")


def decrypt_template(ciphertext: bytes, key: bytes) -> bytes:
    """Authenticate and decrypt an AES-GCM template."""
    if len(key) != 32 or len(ciphertext) < 28:
        raise ValueError("Invalid key or ciphertext")
    return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], b"face-template:v1")
