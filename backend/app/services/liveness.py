"""Basic motion-based challenge check; this is not presentation-attack detection."""

import numpy as np

from app.services.embedding import face_pose


def liveness_failure_reason(frames: list[str], first_turn_sign: int) -> str | None:
    """Validate the server-issued center, turn, opposite turn, and return sequence."""
    # The client captures three frames per phase after the live pose stabilizes.
    if first_turn_sign not in (-1, 1) or len(frames) != 12:
        return "The camera capture was incomplete. Restart and follow all four prompts."

    positions: list[float | None] = []
    for frame in frames:
        try:
            position = float(face_pose(frame))
        except (ValueError, RuntimeError):
            positions.append(None)
            continue
        positions.append(position if np.isfinite(position) else None)

    valid_count = sum(position is not None for position in positions)
    if valid_count < 8:
        return "The face detector lost the face in too many frames. Move closer and use even lighting."

    def phase_median(start: int, end: int) -> float | None:
        valid = [value for value in positions[start:end] if value is not None]
        return float(np.median(valid)) if len(valid) >= 2 else None

    center_start = phase_median(0, 3)
    turn_one = phase_median(3, 6)
    turn_two = phase_median(6, 9)
    center_end = phase_median(9, 12)
    if any(value is None for value in (center_start, turn_one, turn_two, center_end)):
        return "The face was not clear through one of the prompted positions. Keep your full face visible."

    # Compare the neutral baseline to each turn. The sign can be either way
    # because some camera previews are mirrored, but the turns must oppose.
    center = (center_start + center_end) / 2  # type: ignore[operator]
    if abs(center_start - center_end) > 0.16:  # type: ignore[operator]
        return "Return to the same centered position at the beginning and end of the capture."
    delta_one = turn_one - center  # type: ignore[operator]
    delta_two = turn_two - center  # type: ignore[operator]
    min_turn = 0.02
    if abs(delta_one) < min_turn:
        return "The first side turn was too small to detect. Turn a little farther and hold until prompted."
    if abs(delta_two) < min_turn:
        return "The second side turn was too small to detect. Turn a little farther and hold until prompted."
    if delta_one * delta_two >= 0:
        return "The two turns looked like the same direction. Turn to opposite sides of the camera."
    if np.sign(delta_one) != first_turn_sign:
        return "The scan did not match its first direction prompt. Restart and follow the arrow."
    return None


def check_liveness(frames: list[str], first_turn_sign: int) -> bool:
    """Return whether the motion prompt was followed."""
    return liveness_failure_reason(frames, first_turn_sign) is None
