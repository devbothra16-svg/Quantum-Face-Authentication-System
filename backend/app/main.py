"""FastAPI application entry point."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.core.rate_limit import allow_request
from app.db.models import Base
from app.db.session import engine

app = FastAPI(title="Quantum Face Auth", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api")


@app.middleware("http")
async def rate_limit_requests(request: Request, call_next):
    """Limit each client IP before API processing."""
    identity = request.client.host if request.client else "unknown"
    if not allow_request(identity):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


@app.on_event("startup")
def create_tables() -> None:
    """Create development tables; production should apply Alembic migrations."""
    Base.metadata.create_all(bind=engine)
    private_path = Path(settings.jwt_private_key_path)
    public_path = Path(settings.jwt_public_key_path)
    if not private_path.exists() or not public_path.exists():
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(
            private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        public_path.write_bytes(
            private.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
