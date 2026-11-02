"""FastAPI application entry point."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from app.api.routes import router
from app.api.passkeys import router as passkey_router
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
app.include_router(passkey_router, prefix="/api")


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
    # create_all doesn't add columns to an existing development database.
    profile_columns = {
        "full_name": "VARCHAR(120)",
        "department": "VARCHAR(120)",
        "employee_id": "VARCHAR(80)",
    }
    existing_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        for name, sql_type in profile_columns.items():
            if name not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {name} {sql_type}")
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
