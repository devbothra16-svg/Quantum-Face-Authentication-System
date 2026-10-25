"""Liveness challenge interface."""


def check_liveness(frames: list[str], challenge: str) -> bool:
    """Demo liveness guard; requires challenge frames and is not spoof resistant.

    Production wiring must implement MediaPipe landmarks, blink/head movement
    sequence validation and texture corroboration, including freshness checks.
    """
    return len(frames) >= 2 and bool(challenge.strip())
