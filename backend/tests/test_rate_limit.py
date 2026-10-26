"""Rate limiting of expensive endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.rate_limit import RateLimitMiddleware


def _app(monkeypatch, **env) -> TestClient:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/chat")
    def chat():
        return {"ok": True}

    @app.get("/cases/{case_id}/risks")
    def risks(case_id: str):
        return {"ok": True}

    @app.get("/cases")
    def cases():
        return []

    return TestClient(app)


def test_chat_is_limited_per_client(monkeypatch):
    client = _app(monkeypatch)
    codes = [client.post("/chat").status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429

    blocked = client.post("/chat")
    assert int(blocked.headers["Retry-After"]) > 0


def test_limits_are_per_endpoint_and_cheap_routes_are_free(monkeypatch):
    client = _app(monkeypatch, RATE_LIMIT_SCALE="0.1")  # chat → 2/min, risks → 1/min
    assert [client.post("/chat").status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/cases/abc/risks").status_code == 200
    assert client.get("/cases/abc/risks").status_code == 429
    assert all(client.get("/cases").status_code == 200 for _ in range(50))


def test_forwarded_ip_only_trusted_when_enabled(monkeypatch):
    client = _app(monkeypatch, RATE_LIMIT_SCALE="0.05")  # chat → 1/min
    assert client.post("/chat", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # Spoofed header must not reset the limit when the proxy is not trusted
    assert client.post("/chat", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429

    trusted = _app(monkeypatch, RATE_LIMIT_SCALE="0.05", TRUST_PROXY="true")
    assert trusted.post("/chat", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert trusted.post("/chat", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_can_be_disabled(monkeypatch):
    client = _app(monkeypatch, RATE_LIMIT_ENABLED="false")
    assert all(client.post("/chat").status_code == 200 for _ in range(30))
