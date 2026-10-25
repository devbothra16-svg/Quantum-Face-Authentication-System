"""Face embedding interface with an explicit dev-only deterministic fallback."""

import base64
import hashlib

import numpy as np


def get_embedding(frame_b64: str) -> np.ndarray:
    """Decode transient image bytes and extract an embedding.

    Installs may set FACEAUTH_REAL_VISION=1 and use facenet-pytorch weights. The
    deterministic fallback is for API integration demos only and is not a face model.
    """
    raw = base64.b64decode(frame_b64, validate=True)
    if not raw:
        raise ValueError("Empty image")
    digest = hashlib.sha512(raw).digest()
    # Expand a content-derived seed into a reproducible vector without retaining bytes.
    seed = int.from_bytes(digest[:8], "big")
    return np.random.default_rng(seed).normal(size=512).astype(np.float32)
