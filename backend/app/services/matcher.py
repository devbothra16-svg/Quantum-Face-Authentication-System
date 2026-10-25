"""Classical and optional VQC score fusion."""

import numpy as np


def score(
    left: np.ndarray, right: np.ndarray, vqc_score: float | None = None, weight: float = 0.2
) -> float:
    """Return cosine similarity or a convex fusion with an available VQC score."""
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    cosine = float(np.dot(left, right) / denom) if denom else 0.0
    return (1 - weight) * cosine + weight * vqc_score if vqc_score is not None else cosine
