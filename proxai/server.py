"""ProxAI FastAPI proxy server with streaming support."""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from .db import init_db, log_request
from .providers import PROVIDERS, estimate_cost, get_provider_for_path

logger = logging.getLogger("proxai")

app = FastAPI(title="ProxAI", version="0.1.0", docs_url=None, redoc_url=None)

# Rate limiting state: provider -> list of request timestamps
_rate_limit_state: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_RPM = int(os.getenv("PROXAI_RATE_LIMIT_RPM", "60"))


def check_rate_limit(provider_key: str) -> bool:
    """Check if provider is within rate limit. Returns True if allowed."""
    now = time.time()
    window = 60.0
    timestamps = _rate_limit_state[provider_key]
    # Remove timestamps older than 1 minute
    _rate_limit_state[provider_key] = [t for t in timestamps if now - t < window]
    if len(_rate_limit_state[provider_key]) >= RATE_LIMIT_RPM:
        return False
    _rate_limit_state[provider_key].append(now)
    return True


def parse_usage_from_chunk(data: bytes, provider_key: str) -> tuple[int, int, Optional[str]]:
    """Parse token usage and model from response chunks."""
    input_tokens = output_tokens = 0
    model = None
    try:
        # Handle SSE format: data: {...}
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("data: "):
                line = line[6:]
            if not line or line == "[DONE]":
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Model name
            if "model" in obj:
                model = obj["model"]

            # Anthropic: final message_stop event has the authoritative usage block
            if obj.get("type") == "message_delta":
                usage = obj.get("usage", {})
                output_tokens = max(output_tokens, usage.get("output_tokens", 0))
                continue

            # Anthropic: message_start has input token count
            if obj.get("type") == "message_start":
                usage = obj.get("message", {}).get("usage", {})
                input_tokens = max(input_tokens, usage.get("input_tokens", 0))
                continue

            usage = obj.get("usage", {})
            # OpenAI usage format (non-streaming final chunk)
            if "prompt_tokens" in usage:
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

    except Exception:
        pass
    return input_tokens, output_tokens, model


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("ProxAI started — database initialized")


@app.get("/health")
async def health():
    """Health check endpoint."""
    configured = {k: bool(os.getenv(p.env_key)) for k, p in PROVIDERS.items()}
    return {"status": "ok", "providers": configured}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """Main proxy handler — routes requests to the correct AI provider."""
    full_path = "/" + path
    provider_key, provider = get_provider_for_path(full_path)

    if provider is None:
        return Response(
            content=json.dumps({"error": f"No provider for path: {full_path}"}),
            status_code=404,
            media_type="application/json",
        )

    # Rate limiting
    if not check_rate_limit(provider_key):
        return Response(
            content=json.dumps({"error": "Rate limit exceeded"}),
            status_code=429,
            headers={"Retry-After": "60"},
            media_type="application/json",
        )

    # Get real API key
    real_key = os.getenv(provider.env_key, "")
    if not real_key:
        logger.warning(f"No API key configured for {provider.name} ({provider.env_key})")
        return Response(
            content=json.dumps({"error": f"No API key configured for provider: {provider.name}"}),
            status_code=503,
            media_type="application/json",
        )

    # Build upstream URL
    upstream_path = full_path[len(provider.route_prefix):]
    upstream_url = provider.upstream_base + upstream_path

    # Build headers: copy incoming, strip auth, inject real key
    headers = {}
    skip_headers = {"host", "content-length", "transfer-encoding",
                    "authorization", "x-api-key", "connection"}
    for k, v in request.headers.items():
        if k.lower() not in skip_headers:
            headers[k] = v

    headers[provider.auth_header] = f"{provider.auth_prefix}{real_key}"
    headers.update(provider.extra_headers)

    body = await request.body()
    start_time = time.time()

    # Parse request body for model name
    req_model = None
    try:
        req_obj = json.loads(body)
        req_model = req_obj.get("model")
    except Exception:
        pass

    is_streaming = False
    try:
        req_obj_check = json.loads(body) if body else {}
        is_streaming = req_obj_check.get("stream", False)
    except Exception:
        pass

    async def stream_response() -> AsyncIterator[bytes]:
        """Stream upstream response back to client, collecting usage stats."""
        nonlocal req_model
        total_input = total_output = 0
        final_model = req_model
        status = 200
        error_msg = None

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    request.method,
                    upstream_url,
                    headers=headers,
                    content=body,
                    follow_redirects=True,
                ) as upstream:
                    status = upstream.status_code
                    collected = bytearray()
                    async for chunk in upstream.aiter_bytes(chunk_size=4096):
                        collected.extend(chunk)
                        yield chunk

                    # Parse usage from full response
                    inp, out, model_found = parse_usage_from_chunk(bytes(collected), provider_key)
                    total_input += inp
                    total_output += out
                    if model_found:
                        final_model = model_found

        except Exception as e:
            error_msg = str(e)
            status = 502
            yield json.dumps({"error": str(e)}).encode()
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            cost = estimate_cost(final_model or "", total_input, total_output)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                lambda: log_request(
                    provider=provider_key,
                    model=final_model,
                    method=request.method,
                    path=full_path,
                    status_code=status,
                    input_tokens=total_input,
                    output_tokens=total_output,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    error=error_msg,
                ),
            )

    # Determine content type for response
    accept = request.headers.get("accept", "")
    media_type = "text/event-stream" if is_streaming or "event-stream" in accept else "application/json"

    return StreamingResponse(stream_response(), media_type=media_type)
