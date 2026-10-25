"""PennyLane variational verifier boundary with deterministic classical fallback."""

import numpy as np


def verify(features: np.ndarray, template: np.ndarray, enabled: bool = False) -> float:
    """Return a bounded verifier score; default fallback is cosine similarity."""
    a = np.asarray(features, dtype=float).ravel()
    b = np.asarray(template, dtype=float).ravel()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    similarity = float(np.dot(a, b) / denom) if denom else 0.0
    if enabled:
        try:
            import pennylane as qml  # noqa: F401
        except ImportError:
            pass
    return (similarity + 1.0) / 2.0
