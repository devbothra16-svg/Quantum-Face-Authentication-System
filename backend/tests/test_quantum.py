"""Quantum module fallback tests."""

import numpy as np
from app.quantum.qaoa_solver import solve_qubo
from app.quantum.threshold_opt import optimize_threshold
from app.services.matcher import score


def test_qubo_solver_selects_low_energy_subset() -> None:
    """Solver respects cardinality and optimizes a tiny QUBO."""
    result = solve_qubo(np.diag([-2.0, -1.0, 2.0]), 2)
    assert result == [0, 1]


def test_threshold_search_returns_valid_values() -> None:
    """Calibration returns finite threshold and EER values."""
    result = optimize_threshold(np.array([0.9, 0.8, 0.1, 0.2]), np.array([1, 1, 0, 0]))
    assert 0 <= result[0] <= 1
    assert 0 <= result[1] <= 1


def test_match_score() -> None:
    """Cosine matcher returns one for identical vectors."""
    assert np.isclose(score(np.array([1, 2]), np.array([1, 2])), 1.0)


def test_feature_selection_and_vqc_fallbacks() -> None:
    """Classical selector and verifier work without quantum dependencies."""
    from app.quantum.qubo_feature_selection import build_qubo, select_features
    from app.quantum.vqc_verifier import verify

    x = np.array([[0, 1, 2], [1, 0, 1], [4, 1, 0], [5, 0, 0]], dtype=float)
    y = np.array([0, 0, 1, 1])
    assert build_qubo(x, y).shape == (3, 3)
    assert len(select_features(x, y, k=2)) == 2
    assert np.isclose(verify(x[0], x[0]), 1.0)


def test_large_qubo_uses_seeded_fallback() -> None:
    """Larger QUBOs return the requested number of indices reproducibly."""
    q = np.eye(20)
    assert solve_qubo(q, 4, seed=3) == solve_qubo(q, 4, seed=3)
    assert len(solve_qubo(q, 4)) == 4
