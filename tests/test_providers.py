"""Tests for provider routing and cost estimation."""

import pytest
from proxai.providers import get_provider_for_path, estimate_cost, PROVIDERS


def test_anthropic_route():
    key, provider = get_provider_for_path("/anthropic/v1/messages")
    assert key == "anthropic"
    assert provider.name == "Anthropic"
    assert provider.upstream_base == "https://api.anthropic.com"


def test_openai_route():
    key, provider = get_provider_for_path("/openai/chat/completions")
    assert key == "openai"
    assert provider.auth_prefix == "Bearer "


def test_deepseek_route():
    key, provider = get_provider_for_path("/deepseek/chat/completions")
    assert key == "deepseek"


def test_nvidia_route():
    key, provider = get_provider_for_path("/nvidia/chat/completions")
    assert key == "nvidia"


def test_unknown_route_returns_none():
    key, provider = get_provider_for_path("/unknown/path")
    assert key is None
    assert provider is None


def test_root_path_returns_none():
    key, provider = get_provider_for_path("/")
    assert key is None


def test_estimate_cost_known_model():
    cost = estimate_cost("claude-haiku-4-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.8 + 4.0)


def test_estimate_cost_openai():
    cost = estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.15 + 0.6)


def test_estimate_cost_unknown_model():
    cost = estimate_cost("unknown-model-xyz", 100, 100)
    assert cost == 0.0


def test_estimate_cost_zero_tokens():
    cost = estimate_cost("gpt-4o", 0, 0)
    assert cost == 0.0


def test_all_providers_have_required_fields():
    for key, provider in PROVIDERS.items():
        assert provider.name
        assert provider.route_prefix.startswith("/")
        assert provider.upstream_base.startswith("https://")
        assert provider.env_key
        assert provider.auth_header
