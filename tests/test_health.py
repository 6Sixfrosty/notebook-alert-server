from fastapi.testclient import TestClient

from config.settings import get_settings
from server.app import create_app


def test_health_returns_public_service_status(monkeypatch):
    async def fake_init_db():
        return None

    monkeypatch.setattr("server.app.init_db_module.init_db", fake_init_db)
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "alerta-dos-notebooks-api",
        "version": "1.0.0",
    }


def test_ready_returns_ok_when_settings_database_and_startup_are_ok(monkeypatch):
    startup_calls = []

    async def fake_init_db():
        startup_calls.append("called")

    async def fake_ping_database():
        return True

    monkeypatch.setenv("API_TOKEN", "expected-token")
    monkeypatch.setenv("DATABASE_URL", "mongodb://localhost:27017/test")
    get_settings.cache_clear()
    monkeypatch.setattr("server.app.init_db_module.init_db", fake_init_db)
    monkeypatch.setattr("server.routes.health.ping_database", fake_ping_database)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")

    body = response.json()
    assert startup_calls == ["called"]
    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["checks"] == {
        "settings": "ok",
        "database": "ok",
    }


def test_ready_returns_not_ready_without_exposing_secrets(monkeypatch):
    async def fake_init_db():
        raise RuntimeError("mongodb://user:password@localhost:27017/test")

    async def fake_ping_database():
        return False

    monkeypatch.setenv("API_TOKEN", "secret-token")
    monkeypatch.setenv("DATABASE_URL", "mongodb://user:password@localhost:27017/test")
    get_settings.cache_clear()
    monkeypatch.setattr("server.app.init_db_module.init_db", fake_init_db)
    monkeypatch.setattr("server.routes.health.ping_database", fake_ping_database)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")

    serialized = str(response.json())
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "secret-token" not in serialized
    assert "mongodb://user:password@localhost:27017/test" not in serialized


def test_main_exposes_fastapi_app():
    from main import app

    assert app.title == "Alerta dos Notebooks API"
