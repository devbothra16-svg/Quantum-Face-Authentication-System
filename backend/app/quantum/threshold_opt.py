"""Decision threshold and fusion-weight calibration."""

import numpy as np
from sklearn.metrics import roc_curve


def optimize_threshold(
    scores: np.ndarray, labels: np.ndarray, weights: tuple[float, ...] = (0.0, 0.2, 0.4)
) -> tuple[float, float, float]:
    """Search deterministic threshold/weight grid for minimum empirical EER."""
    best = (1.0, 0.0, 0.0)
    for weight in weights:
        fused = np.asarray(scores)
        fpr, tpr, thresholds = roc_curve(labels, fused)
        fnr = 1 - tpr
        idx = int(np.argmin(np.abs(fpr - fnr)))
        eer = float((fpr[idx] + fnr[idx]) / 2)
        if eer < best[0]:
            best = (eer, float(thresholds[idx]), float(weight))
    return best
