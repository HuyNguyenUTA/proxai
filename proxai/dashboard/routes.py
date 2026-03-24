"""Dashboard routes — stats and recent requests UI."""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..db import get_recent_requests, get_stats, get_today_stats
from ..providers import PROVIDERS

dashboard_app = FastAPI(title="ProxAI Dashboard", docs_url=None)

_TEMPLATE = Path(__file__).parent / "templates" / "index.html"


@dashboard_app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_TEMPLATE.read_text())


@dashboard_app.get("/api/stats")
async def api_stats():
    today = get_today_stats()
    monthly = get_stats(days=30)
    recent = get_recent_requests(limit=50)
    return {
        "today": today,
        "monthly": monthly,
        "recent": recent,
    }


@dashboard_app.get("/api/health")
async def api_health():
    return {
        k: bool(os.getenv(p.env_key))
        for k, p in PROVIDERS.items()
    }


class TestRequest(BaseModel):
    provider: str
    model: str
    message: str
    max_tokens: int = 512


@dashboard_app.post("/api/test")
async def api_test(req: TestRequest):
    """Send a test request through the proxy and return the response."""
    proxy_host = os.getenv("PROXAI_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXAI_PORT", "8090")
    provider = PROVIDERS.get(req.provider)

    if not provider:
        return {"error": f"Unknown provider: {req.provider}"}

    # Build request for this provider
    if req.provider == "anthropic":
        url = f"http://{proxy_host}:{proxy_port}/anthropic/v1/messages"
        headers = {"x-api-key": "proxied", "Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        body = {"model": req.model, "max_tokens": req.max_tokens,
                "messages": [{"role": "user", "content": req.message}]}
    else:
        url = f"http://{proxy_host}:{proxy_port}/{req.provider}/chat/completions"
        headers = {"Authorization": "Bearer proxied", "Content-Type": "application/json"}
        body = {"model": req.model, "max_tokens": req.max_tokens,
                "messages": [{"role": "user", "content": req.message}]}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        return {"status": resp.status_code, "body": resp.json()}
    except Exception as e:
        return {"error": str(e)}
