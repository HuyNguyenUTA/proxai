"""Dashboard routes — stats and recent requests UI."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ..db import get_recent_requests, get_stats, get_today_stats

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
    from ..providers import PROVIDERS
    return {
        k: bool(os.getenv(p.env_key))
        for k, p in PROVIDERS.items()
    }
