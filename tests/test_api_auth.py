import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from config.settings import get_settings
from server.auth import require_api_token
from server.errors import register_exception_handlers


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("API_TOKEN", "expected-token")
    monkeypatch.setenv("DATABASE_URL", "mongodb://localhost:27017/test")
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/admin", dependencies=[Depends(require_api_token)])
    async def admin_route():
        return {"ok": True}

    return TestClient(app)


def test_request_without_token_returns_401(client):
    response = client.get("/admin")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING"
    assert response.json()["error"]["field"] is None
    assert response.json()["error"]["request_id"].startswith("req_")


def test_request_with_wrong_token_returns_403(client):
    response = client.get(
        "/admin",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "AUTH_INVALID"
    assert body["error"]["message"] == "Token inválido."
    assert "wrong-token" not in str(body)


def test_request_with_correct_token_is_allowed(client):
    response = client.get(
        "/admin",
        headers={"Authorization": "Bearer expected-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_token_in_query_string_is_not_accepted(client):
    response = client.get("/admin?token=expected-token")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING"


def test_error_response_uses_standard_shape(client):
    response = client.get("/admin", headers={"X-Request-ID": "req-test"})

    assert response.json() == {
        "error": {
            "code": "AUTH_MISSING",
            "message": "Token ausente.",
            "field": None,
            "request_id": "req-test",
        }
    }
