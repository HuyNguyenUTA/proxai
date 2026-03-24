"""Tests for proxy server logic."""

import json
import pytest
from proxai.server import parse_usage_from_chunk, check_rate_limit, _rate_limit_state


# ── Token parsing ─────────────────────────────────────────────────────────────

def test_parse_anthropic_streaming():
    """Anthropic SSE: message_start has input tokens, message_delta has output tokens."""
    data = "\n".join([
        'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
        'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":5}}',
        'data: {"type":"message_stop"}',
    ]).encode()

    inp, out, model = parse_usage_from_chunk(data, "anthropic")
    assert inp == 10
    assert out == 5


def test_parse_openai_non_streaming():
    """OpenAI non-streaming response with usage block."""
    data = json.dumps({
        "model": "gpt-4o-mini",
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 15,
        }
    }).encode()

    inp, out, model = parse_usage_from_chunk(data, "openai")
    assert inp == 20
    assert out == 15
    assert model == "gpt-4o-mini"


def test_parse_extracts_model_name():
    data = json.dumps({"model": "claude-haiku-4-5", "usage": {}}).encode()
    _, _, model = parse_usage_from_chunk(data, "anthropic")
    assert model == "claude-haiku-4-5"


def test_parse_empty_data():
    inp, out, model = parse_usage_from_chunk(b"", "anthropic")
    assert inp == 0
    assert out == 0
    assert model is None


def test_parse_invalid_json_does_not_crash():
    inp, out, model = parse_usage_from_chunk(b"not json at all }{", "openai")
    assert inp == 0
    assert out == 0


def test_parse_done_sentinel_ignored():
    data = b"data: [DONE]\n"
    inp, out, model = parse_usage_from_chunk(data, "openai")
    assert inp == 0
    assert out == 0


def test_no_anthropic_double_count():
    """Output tokens should not be double-counted from message_delta."""
    data = "\n".join([
        'data: {"type":"message_start","message":{"usage":{"input_tokens":8}}}',
        'data: {"type":"message_delta","usage":{"output_tokens":25}}',
    ]).encode()

    inp, out, _ = parse_usage_from_chunk(data, "anthropic")
    assert out == 25  # not 50


# ── Rate limiting ─────────────────────────────────────────────────────────────

def setup_function():
    _rate_limit_state.clear()


def test_rate_limit_allows_under_limit():
    assert check_rate_limit("test-provider") is True


def test_rate_limit_blocks_over_limit(monkeypatch):
    import proxai.server as srv
    monkeypatch.setattr(srv, "RATE_LIMIT_RPM", 3)
    _rate_limit_state.clear()

    assert check_rate_limit("test-provider") is True
    assert check_rate_limit("test-provider") is True
    assert check_rate_limit("test-provider") is True
    assert check_rate_limit("test-provider") is False  # 4th request blocked


def test_rate_limit_separate_per_provider():
    _rate_limit_state.clear()
    assert check_rate_limit("anthropic") is True
    assert check_rate_limit("openai") is True
