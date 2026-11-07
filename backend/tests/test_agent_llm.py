"""Tests for the LLM client.  Uses httpx.MockTransport — never the real API."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.services.llm_client import (
    LLMUnavailable,
    _cache_key,
    complete_json,
)


# ---------------------------------------------------------------------------
# Test schema — extra="forbid", no defaults, as required by Groq strict mode
# ---------------------------------------------------------------------------

class DummySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    greeting: str
    count: int


VALID_RESPONSE = '{"greeting": "hello", "count": 42}'
INVALID_RESPONSE = '{"greeting": "hello"}'  # missing "count"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(**overrides) -> Settings:
    overrides.setdefault("frontend_origin", "http://localhost:5173")
    overrides.setdefault("groq_api_key", "test-key")
    overrides.setdefault("groq_model", "test-model")
    return Settings(_env_file=None, **overrides)


def _groq_success_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _run(coro):
    """Run an async coroutine synchronously in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _AsyncTransport(httpx.AsyncBaseTransport):
    """Async transport that returns pre-built responses in sequence."""

    def __init__(self, responses: list[httpx.Response]):
        self._responses = responses
        self._idx = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        idx = self._idx
        self._idx += 1
        if idx < len(self._responses):
            return self._responses[idx]
        raise RuntimeError(f"_AsyncTransport: unexpected call #{idx + 1}")


def _patch_groq(monkeypatch, responses: list[httpx.Response]):
    """Replace _groq_client so it returns an AsyncClient backed by fake responses."""
    transport = _AsyncTransport(responses)

    def fake_groq_client(settings, timeout=60):
        return httpx.AsyncClient(transport=transport, base_url="https://fake")

    monkeypatch.setattr("app.services.llm_client._groq_client", fake_groq_client)


# ---------------------------------------------------------------------------
# Saved mode
# ---------------------------------------------------------------------------

def test_saved_mode_returns_cached_reply(tmp_path: Path, monkeypatch):
    """When llm_mode='saved' and a cache file exists, return the cached response."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)

    settings = _settings(llm_mode="saved")
    key = _cache_key(settings.groq_model, [{"role": "user", "content": "hi"}], "DummySchema")
    (tmp_path / f"{key}.json").write_text(VALID_RESPONSE, encoding="utf-8")

    result = _run(complete_json(
        step="test",
        messages=[{"role": "user", "content": "hi"}],
        schema=DummySchema,
        run_id=None,
        settings=settings,
    ))
    assert result.greeting == "hello"
    assert result.count == 42


def test_saved_mode_raises_when_no_cache(tmp_path: Path, monkeypatch):
    """When llm_mode='saved' and there is no cache file, raise LLMUnavailable."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)

    settings = _settings(llm_mode="saved")

    with pytest.raises(LLMUnavailable, match="No cached response"):
        _run(complete_json(
            step="test",
            messages=[{"role": "user", "content": "hi"}],
            schema=DummySchema,
            run_id=None,
            settings=settings,
        ))


# ---------------------------------------------------------------------------
# Live mode – 429 handling
# ---------------------------------------------------------------------------

def test_429_then_success(tmp_path: Path, monkeypatch):
    """A 429 followed by a 200 returns the result."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(429, headers={"retry-after": "0"}),
        httpx.Response(200, json=_groq_success_body(VALID_RESPONSE)),
    ])

    settings = _settings(llm_mode="live")
    result = _run(complete_json(
        step="test",
        messages=[{"role": "user", "content": "hi"}],
        schema=DummySchema,
        run_id=None,
        settings=settings,
    ))
    assert result.greeting == "hello"
    assert result.count == 42


def test_all_429s_raises(tmp_path: Path, monkeypatch):
    """When every attempt gets a 429, raise LLMUnavailable."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(429, headers={"retry-after": "0"}),
        httpx.Response(429, headers={"retry-after": "0"}),
        httpx.Response(429, headers={"retry-after": "0"}),
    ])

    settings = _settings(llm_mode="live")
    with pytest.raises(LLMUnavailable, match="429"):
        _run(complete_json(
            step="test",
            messages=[{"role": "user", "content": "hi"}],
            schema=DummySchema,
            run_id=None,
            settings=settings,
        ))


# ---------------------------------------------------------------------------
# Live mode – validation retry
# ---------------------------------------------------------------------------

def test_invalid_json_once_then_valid(tmp_path: Path, monkeypatch):
    """Invalid JSON on the first attempt is retried; the second valid attempt succeeds."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(200, json=_groq_success_body(INVALID_RESPONSE)),
        httpx.Response(200, json=_groq_success_body(VALID_RESPONSE)),
    ])

    settings = _settings(llm_mode="live")
    result = _run(complete_json(
        step="test",
        messages=[{"role": "user", "content": "hi"}],
        schema=DummySchema,
        run_id=None,
        settings=settings,
    ))
    assert result.greeting == "hello"
    assert result.count == 42


def test_invalid_json_twice_raises(tmp_path: Path, monkeypatch):
    """Two invalid responses in a row raise LLMUnavailable."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(200, json=_groq_success_body(INVALID_RESPONSE)),
        httpx.Response(200, json=_groq_success_body(INVALID_RESPONSE)),
    ])

    settings = _settings(llm_mode="live")
    with pytest.raises(LLMUnavailable, match="Validation failed twice"):
        _run(complete_json(
            step="test",
            messages=[{"role": "user", "content": "hi"}],
            schema=DummySchema,
            run_id=None,
            settings=settings,
        ))


# ---------------------------------------------------------------------------
# Live mode – Groq rejecting its own generation (400 json_validate_failed)
# ---------------------------------------------------------------------------

SCHEMA_MISMATCH = {
    "error": {
        "message": "Generated JSON does not match the expected schema. Please adjust your prompt.",
        "type": "invalid_request_error",
        "code": "json_validate_failed",
    }
}


def test_schema_mismatch_400_once_then_success(tmp_path: Path, monkeypatch):
    """Groq's 'generated JSON does not match the schema' 400 is retried once."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(400, json=SCHEMA_MISMATCH),
        httpx.Response(200, json=_groq_success_body(VALID_RESPONSE)),
    ])

    result = _run(complete_json(
        step="test",
        messages=[{"role": "user", "content": "hi"}],
        schema=DummySchema,
        run_id=None,
        settings=_settings(llm_mode="live"),
    ))
    assert result.count == 42


def test_schema_mismatch_400_twice_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(400, json=SCHEMA_MISMATCH),
        httpx.Response(400, json=SCHEMA_MISMATCH),
    ])

    with pytest.raises(LLMUnavailable, match="400"):
        _run(complete_json(
            step="test",
            messages=[{"role": "user", "content": "hi"}],
            schema=DummySchema,
            run_id=None,
            settings=_settings(llm_mode="live"),
        ))


def test_other_400_is_not_retried(tmp_path: Path, monkeypatch):
    """Any other 400 (a bad request) fails at once; the fake transport has no second reply."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(400, json={"error": {"message": "model not found", "code": "model_not_found"}}),
    ])

    with pytest.raises(LLMUnavailable, match="model not found"):
        _run(complete_json(
            step="test",
            messages=[{"role": "user", "content": "hi"}],
            schema=DummySchema,
            run_id=None,
            settings=_settings(llm_mode="live"),
        ))


# ---------------------------------------------------------------------------
# Caching in live mode
# ---------------------------------------------------------------------------

def test_live_mode_writes_cache_on_success(tmp_path: Path, monkeypatch):
    """A successful live call writes the response to the cache directory."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)
    monkeypatch.setattr("app.services.llm_client._log_llm_call", lambda **kw: None)

    _patch_groq(monkeypatch, [
        httpx.Response(200, json=_groq_success_body(VALID_RESPONSE)),
    ])

    settings = _settings(llm_mode="live")
    messages = [{"role": "user", "content": "hi"}]

    _run(complete_json(
        step="test",
        messages=messages,
        schema=DummySchema,
        run_id=None,
        settings=settings,
    ))

    key = _cache_key(settings.groq_model, messages, "DummySchema")
    cached = (tmp_path / f"{key}.json").read_text(encoding="utf-8")
    assert json.loads(cached) == json.loads(VALID_RESPONSE)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_live_mode_logs_llm_call(tmp_path: Path, monkeypatch):
    """A successful live call invokes _log_llm_call with ok=True."""
    monkeypatch.setattr("app.services.llm_client.CACHE_DIR", tmp_path)

    logged = {}

    def capture_log(**kwargs):
        logged.update(kwargs)

    monkeypatch.setattr("app.services.llm_client._log_llm_call", capture_log)

    _patch_groq(monkeypatch, [
        httpx.Response(200, json=_groq_success_body(VALID_RESPONSE)),
    ])

    settings = _settings(llm_mode="live")
    run_id = uuid.uuid4()
    _run(complete_json(
        step="diagnose",
        messages=[{"role": "user", "content": "hi"}],
        schema=DummySchema,
        run_id=run_id,
        settings=settings,
    ))

    assert logged["ok"] is True
    assert logged["step"] == "diagnose"
    assert logged["model"] == "test-model"
    assert logged["run_id"] == run_id
    assert logged["input_tokens"] == 10
    assert logged["output_tokens"] == 5
    assert logged["latency_ms"] >= 0
