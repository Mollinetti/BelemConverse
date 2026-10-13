"""mvp-2: only the project's pages origin may call the API from a browser."""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.main import cors_options

PAGES = "https://mollinetti.github.io"


def preflight(client, origin):
    return client.options(
        "/api/chat",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
    )


def app_with(monkeypatch, allowed):
    if allowed is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", allowed)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, **cors_options())

    @app.post("/api/chat")
    def chat():
        return {}

    return TestClient(app)


def test_pages_origin_allowed(monkeypatch):
    client = app_with(monkeypatch, PAGES)

    response = preflight(client, PAGES)

    assert response.headers.get("access-control-allow-origin") == PAGES
    assert "access-control-allow-credentials" not in response.headers


def test_other_origin_refused(monkeypatch):
    client = app_with(monkeypatch, PAGES)

    assert "access-control-allow-origin" not in preflight(client, "https://evil.example").headers


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8080"])
def test_localhost_allowed_when_unset(monkeypatch, origin):
    client = app_with(monkeypatch, None)

    response = preflight(client, origin)

    assert response.headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "http://localhost.evil.example", "https://localhost:5173"]
)
def test_only_plain_localhost_when_unset(monkeypatch, origin):
    client = app_with(monkeypatch, None)

    assert "access-control-allow-origin" not in preflight(client, origin).headers


def test_real_app_refuses_other_origins(client):
    response = preflight(client, "https://evil.example")

    assert "access-control-allow-origin" not in response.headers
