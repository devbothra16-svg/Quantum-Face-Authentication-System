"""Deterministic synthetic protocol smoke evaluation.

Use --lfw-dir for actual LFW image data. Synthetic numbers are clearly labelled
and are not evidence of biometric performance.
"""

import argparse
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, roc_curve


def evaluate(seed: int = 1729) -> dict[str, float]:
    """Generate a deterministic toy verification set for wiring checks only."""
    rng = np.random.default_rng(seed)
    genuine = rng.normal(0.75, 0.12, 400)
    impostor = rng.normal(0.25, 0.12, 400)
    scores = np.concatenate((genuine, impostor)).clip(0, 1)
    labels = np.concatenate((np.ones(400), np.zeros(400)))
    fpr, tpr, thresholds = roc_curve(labels, scores)
    fnr = 1 - tpr
    index = int(np.argmin(np.abs(fpr - fnr)))
    threshold = thresholds[index]
    predictions = scores >= threshold
    return {
        "eer": float((fpr[index] + fnr[index]) / 2),
        "accuracy": float(accuracy_score(labels, predictions)),
        "far": float(np.mean(predictions[400:])),
        "frr": float(np.mean(~predictions[:400])),
        "threshold": float(threshold),
    }


def main() -> None:
    """Write the deterministic protocol smoke result report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/RESULTS.md")
    parser.add_argument("--lfw-dir", help="LFW directory (not yet wired in the demo evaluator)")
    args = parser.parse_args()
    result = evaluate()
    content = "# Results\n\n## Protocol smoke check\n\nThese reproducible numbers are from a synthetic score distribution, not facial imagery and not an LFW benchmark. They verify evaluation/report plumbing only.\n\n| EER | Accuracy | FAR | FRR | Threshold |\n|---:|---:|---:|---:|---:|\n| {eer:.4f} | {accuracy:.4f} | {far:.4f} | {frr:.4f} | {threshold:.4f} |\n\nReal LFW evaluation is not available until the pretrained face model and dataset are provisioned. Do not interpret this table as authentication performance.\n".format(
        **result
    )
    Path(args.output).write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
