"""Feature selection QUBO and classical baselines."""

import numpy as np
from sklearn.feature_selection import mutual_info_classif
from sklearn.preprocessing import StandardScaler


def build_qubo(x: np.ndarray, y: np.ndarray, redundancy: float = 0.25) -> np.ndarray:
    """Build a binary quadratic objective rewarding class separation and penalizing correlation."""
    values = StandardScaler().fit_transform(np.asarray(x))
    labels = np.asarray(y)
    means = [values[labels == label].mean(axis=0) for label in np.unique(labels)]
    relevance = np.var(means, axis=0)
    corr = np.nan_to_num(np.corrcoef(values, rowvar=False))
    q = -np.diag(relevance)
    q += redundancy * (np.abs(corr) - np.eye(corr.shape[0]))
    return q


def select_features(
    x: np.ndarray, y: np.ndarray, k: int = 24, use_quantum: bool = False, seed: int = 1729
) -> np.ndarray:
    """Select top-k features using MI or optional QAOA, falling back to MI."""
    k = min(k, x.shape[1])
    if use_quantum:
        try:
            from .qaoa_solver import solve_qubo

            chosen = solve_qubo(build_qubo(x, y), k, seed)
            if chosen:
                return np.array(sorted(chosen))
        except (ImportError, RuntimeError, ValueError):
            pass
    relevance = mutual_info_classif(x, y, random_state=seed)
    return np.argsort(relevance)[-k:]
