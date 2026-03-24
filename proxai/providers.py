"""AI provider definitions and model pricing."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Provider:
    """Definition of an AI API provider."""
    name: str
    route_prefix: str        # e.g. /anthropic
    upstream_base: str       # e.g. https://api.anthropic.com
    auth_header: str         # Header to inject key into
    auth_prefix: str         # e.g. "Bearer " or ""
    env_key: str             # .env variable name
    extra_headers: dict = field(default_factory=dict)


# Provider registry
PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        name="Anthropic",
        route_prefix="/anthropic",
        upstream_base="https://api.anthropic.com",
        auth_header="x-api-key",
        auth_prefix="",
        env_key="ANTHROPIC_API_KEY",
        extra_headers={"anthropic-version": "2023-06-01"},
    ),
    "openai": Provider(
        name="OpenAI",
        route_prefix="/openai",
        upstream_base="https://api.openai.com/v1",
        auth_header="Authorization",
        auth_prefix="Bearer ",
        env_key="OPENAI_API_KEY",
    ),
    "deepseek": Provider(
        name="DeepSeek",
        route_prefix="/deepseek",
        upstream_base="https://api.deepseek.com/v1",
        auth_header="Authorization",
        auth_prefix="Bearer ",
        env_key="DEEPSEEK_API_KEY",
    ),
    "nvidia": Provider(
        name="NVIDIA NIM",
        route_prefix="/nvidia",
        upstream_base="https://integrate.api.nvidia.com/v1",
        auth_header="Authorization",
        auth_prefix="Bearer ",
        env_key="NVIDIA_API_KEY",
    ),
}

# Model pricing (per 1M tokens, USD)
MODEL_PRICING: dict[str, dict] = {
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022":  {"input": 0.8, "output": 4.0},
    "claude-opus-4-5":            {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5":          {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5":           {"input": 0.8, "output": 4.0},
    # OpenAI
    "gpt-4o":                     {"input": 2.5, "output": 10.0},
    "gpt-4o-mini":                {"input": 0.15, "output": 0.6},
    "gpt-4-turbo":                {"input": 10.0, "output": 30.0},
    # DeepSeek
    "deepseek-chat":              {"input": 0.27, "output": 1.1},
    "deepseek-reasoner":          {"input": 0.55, "output": 2.19},
    # NVIDIA NIM (approximate)
    "meta/llama-3.1-70b-instruct": {"input": 0.35, "output": 0.4},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a request."""
    # Exact match first, then prefix match (handles date-suffixed model names
    # e.g. claude-haiku-4-5-20251001 matches claude-haiku-4-5)
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        for key, p in MODEL_PRICING.items():
            if model.startswith(key):
                pricing = p
                break
    if not pricing:
        return 0.0
    return (
        (input_tokens / 1_000_000) * pricing["input"] +
        (output_tokens / 1_000_000) * pricing["output"]
    )


def get_provider_for_path(path: str) -> Optional[tuple[str, Provider]]:
    """Find the provider matching a given request path."""
    for key, provider in PROVIDERS.items():
        if path.startswith(provider.route_prefix):
            return key, provider
    return None, None
