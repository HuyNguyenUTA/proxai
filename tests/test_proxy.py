"""Integration tests for the proxy endpoint using HTTPX test client."""

import json
import os
import pytest
from httpx import AsyncClient, ASGITransport

from proxai.server import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def anthropic_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")


@pytest.mark.anyio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "providers" in data


@pytest.mark.anyio
async def test_unknown_route_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/unknown/path", json={"model": "test"})
    assert resp.status_code == 404
    assert "error" in resp.json()


@pytest.mark.anyio
async def test_missing_api_key_returns_503(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/anthropic/v1/messages",
            json={"model": "claude-haiku-4-5", "max_tokens": 10,
                  "messages": [{"role": "user", "content": "hi"}]},
            headers={"x-api-key": "proxied"},
        )
    assert resp.status_code == 503
    assert "error" in resp.json()


@pytest.mark.anyio
async def test_rate_limit_returns_429(monkeypatch):
    import proxai.server as srv
    monkeypatch.setattr(srv, "RATE_LIMIT_RPM", 0)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    srv._rate_limit_state.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/anthropic/v1/messages",
            json={"model": "claude-haiku-4-5", "max_tokens": 10,
                  "messages": [{"role": "user", "content": "hi"}]},
            headers={"x-api-key": "proxied"},
        )
    assert resp.status_code == 429
    assert resp.headers.get("retry-after") == "60"
