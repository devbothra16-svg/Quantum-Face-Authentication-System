"""Service boundary tests."""

import base64

import numpy as np
from app.services.embedding import get_embedding
from app.services.liveness import check_liveness


def test_demo_embedding_is_deterministic() -> None:
    """The fallback vector is repeatable and dimensioned as documented."""
    image = base64.b64encode(b"transient bytes").decode()
    assert np.array_equal(get_embedding(image), get_embedding(image))
    assert get_embedding(image).shape == (512,)


def test_liveness_requires_multiple_frames_and_challenge() -> None:
    """Demo liveness gate rejects missing challenge material."""
    assert check_liveness(["a", "b"], "blink")
    assert not check_liveness(["a"], "blink")
    assert not check_liveness(["a", "b"], " ")
