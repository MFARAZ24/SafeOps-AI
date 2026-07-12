from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """The API root endpoint should return application information."""

    response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "SafeOps AI API"
    assert body["status"] == "running"
    assert body["documentation"] == "/docs"


def test_health_endpoint() -> None:
    """The health endpoint should report a healthy API."""

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert body["service"] == "SafeOps AI API"
    assert body["version"] == "0.1.0"
    assert body["environment"] == "development"
