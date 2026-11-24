from fastapi.testclient import TestClient

from orinoco.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "orinoco"


def test_root_endpoint_identifies_application() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Orinoco"
