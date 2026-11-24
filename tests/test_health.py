from fastapi.testclient import TestClient

from orinoco import main
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


def test_ready_endpoint_returns_ready_when_model_is_present(monkeypatch) -> None:
    async def ready_status() -> dict[str, str]:
        return {
            "status": "ready",
            "service": "orinoco",
            "model": "qwen2.5:1.5b",
        }

    monkeypatch.setattr(main, "get_ollama_readiness", ready_status)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_endpoint_returns_503_when_model_is_missing(monkeypatch) -> None:
    async def missing_status() -> dict[str, str]:
        return {
            "status": "model_missing",
            "service": "orinoco",
            "model": "qwen2.5:1.5b",
        }

    monkeypatch.setattr(main, "get_ollama_readiness", missing_status)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "model_missing"
