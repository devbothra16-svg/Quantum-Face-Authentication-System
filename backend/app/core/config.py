"""Typed application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings with safe development defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./faceauth.db"
    redis_url: str = "redis://localhost:6379/0"
    kms_key_path: str = "./dev-template.key"
    jwt_private_key_path: str = "./dev-jwt-private.pem"
    jwt_public_key_path: str = "./dev-jwt-public.pem"
    use_quantum: bool = False
    quantum_backend: str = "simulator"
    feature_count: int = 24
    vqc_weight: float = 0.2
    access_token_minutes: int = 5
    face_detector_model: str = "/models/face_detection_yunet_2023mar.onnx"
    face_recognition_model: str = "/models/face_recognition_sface_2021dec.onnx"
    face_match_threshold: float = 0.363
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Identity Access Demo"
    webauthn_origin: str = "http://localhost:5173"
    seed: int = 1729
    cors_origins: str = "http://localhost"


settings = Settings()
