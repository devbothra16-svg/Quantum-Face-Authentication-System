"""API smoke tests."""

from app.main import app
from fastapi.testclient import TestClient


def test_health_endpoint() -> None:
    """Health endpoint advertises service readiness."""
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
