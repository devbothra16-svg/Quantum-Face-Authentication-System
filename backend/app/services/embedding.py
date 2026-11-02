"""Local face detection and SFace embeddings; raw frames are never persisted."""

import base64
import binascii
import threading

import cv2
import numpy as np

from app.core.config import settings

_lock = threading.Lock()
_detect_lock = threading.Lock()
_recognize_lock = threading.Lock()
_detector = None
_recognizer = None


def _models():
    """Load the small OpenCV Zoo YuNet and SFace ONNX models once per process."""
    global _detector, _recognizer
    if _detector is None or _recognizer is None:
        with _lock:
            if _detector is None or _recognizer is None:
                if not settings.face_detector_model or not settings.face_recognition_model:
                    raise RuntimeError("Face recognition models are not configured")
                _detector = cv2.FaceDetectorYN.create(
                    settings.face_detector_model, "", (320, 320), 0.85, 0.3, 5000
                )
                _recognizer = cv2.FaceRecognizerSF.create(
                    settings.face_recognition_model, ""
                )
    return _detector, _recognizer


def _decode_frame(frame_b64: str) -> np.ndarray:
    """Decode one base64 image frame into BGR pixels with strict size checks."""
    try:
        raw = base64.b64decode(frame_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("A camera frame was invalid") from exc
    if not raw or len(raw) > 2_000_000:
        raise ValueError("Camera frame is empty or too large")
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] < 160 or image.shape[1] < 160:
        raise ValueError("Camera frame could not be decoded or is too small")
    return image


def _detect(image: np.ndarray, min_score: float = 0.85, min_size: float = 80):
    detector, _ = _models()
    with _detect_lock:
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
    if faces is None or len(faces) != 1:
        raise ValueError("Keep exactly one face in view")
    face = faces[0]
    if float(face[14]) < min_score or min(float(face[2]), float(face[3])) < min_size:
        raise ValueError("Move closer and face the camera in good light")
    return face


def get_embedding(frame_b64: str) -> np.ndarray:
    """Extract a normalized SFace identity vector from a single face frame."""
    image = _decode_frame(frame_b64)
    face = _detect(image)
    _, recognizer = _models()
    with _recognize_lock:
        aligned = recognizer.alignCrop(image, face)
        feature = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(feature))
    if not norm or not np.isfinite(feature).all():
        raise ValueError("Could not extract a usable face template")
    return feature / norm


def face_pose(frame_b64: str) -> float:
    """Return normalized nose position between the eye landmarks for turn checks."""
    image = _decode_frame(frame_b64)
    # Motion checks need to tolerate mild blur while the head is turning.
    # Identity extraction retains the stricter default detector thresholds.
    face = _detect(image, min_score=0.65, min_size=64)
    left_eye_x, right_eye_x, nose_x = float(face[4]), float(face[6]), float(face[8])
    eye_span = abs(right_eye_x - left_eye_x)
    if eye_span < 10:
        raise ValueError("Face landmarks are not clear enough; improve the lighting")
    return (nose_x - min(left_eye_x, right_eye_x)) / eye_span
