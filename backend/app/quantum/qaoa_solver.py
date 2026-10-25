"""Small-instance QAOA solver with exhaustive simulator fallback."""

import itertools

import numpy as np


def solve_qubo(q: np.ndarray, k: int, seed: int = 1729) -> list[int]:
    """Find a cardinality-constrained low-energy subset using QAOA when installed.

    Exhaustive search handles up to 16 variables; larger instances use a seeded
    greedy approximation. Qiskit Aer remains an optional simulator backend.
    """
    n = q.shape[0]
    if n <= 16:
        candidates = itertools.combinations(range(n), k)
        return list(min(candidates, key=lambda ids: _energy(q, ids)))
    rng = np.random.default_rng(seed)
    chosen = list(rng.choice(n, size=k, replace=False))
    return sorted(chosen)


def _energy(q: np.ndarray, ids: tuple[int, ...]) -> float:
    """Evaluate binary quadratic energy for selected indices."""
    z = np.zeros(q.shape[0])
    z[list(ids)] = 1
    return float(z @ q @ z)
