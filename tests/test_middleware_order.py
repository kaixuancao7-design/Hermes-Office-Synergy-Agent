import importlib

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.config import settings


def test_middleware_order_rejections_preflight_and_spoofing(monkeypatch, caplog):
    monkeypatch.setattr(settings, "LOG_OUTPUTS", "console")
    main = importlib.import_module("src.main")
    assert [entry.cls.__name__ for entry in main.app.user_middleware] == [
        "CORSMiddleware", "RequestLoggingMiddleware", "ResponseLoggingMiddleware",
        "RateLimitMiddleware", "APIKeyMiddleware"]
    monkeypatch.setattr(settings, "API_KEY_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEYS", "")
    monkeypatch.setattr(settings, "API_KEY_USERS", '{"secret-token":"alice"}')
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_REQUESTS", 2)
    app = FastAPI()
    # Copy the actual application's middleware chain without external startup.
    app.user_middleware = list(main.app.user_middleware)

    @app.get("/private")
    def private():
        return {"ok": True}

    @app.get("/handled-error")
    def handled_error():
        raise HTTPException(400, "bad input")

    origin = settings.ALLOWED_ORIGINS.split(",")[0]
    if origin == "*":
        origin = "http://localhost"
    headers = {"Origin": origin, "X-Request-ID": "test-request"}
    with TestClient(app) as client:
        first = client.get("/private", headers=headers)
        assert first.status_code == 401
        normal = client.get("/private", headers={**headers, "X-API-Key": "secret-token"})
        assert normal.status_code == 200
        blocked = client.get("/private", headers={**headers, "X-User-ID": "forged-other-user"})
        assert blocked.status_code == 429
        for response in (first, normal, blocked):
            assert response.headers["X-Request-ID"] == "test-request"
            assert "access-control-allow-origin" in response.headers
        preflight = client.options("/private", headers={**headers,
            "Access-Control-Request-Method": "GET"})
        assert preflight.status_code == 200
        # A separate client IP gets an independent window.
    with TestClient(app, client=("other-client", 123)) as client:
        error = client.get("/handled-error", headers={**headers, "X-API-Key": "secret-token"})
        assert error.status_code == 400
        assert error.headers["X-Request-ID"] == "test-request"
        assert "access-control-allow-origin" in error.headers
    assert "secret-token" not in caplog.text
