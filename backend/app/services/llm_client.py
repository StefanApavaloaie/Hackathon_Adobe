"""LLM client: every agent step calls complete_json() and nothing else.

Supports two modes controlled by settings.llm_mode:
  - "saved"  → replay cached responses (zero tokens spent)
  - "live"   → call Groq, with 429-retry, validation-retry, and caching
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "llm_cache"

MAX_RETRIES = 3          # total attempts on 429
MAX_RETRY_WAIT = 30      # seconds, cap for retry-after header
TEMPERATURE = 0.3


class LLMUnavailable(Exception):
    """Raised when the LLM cannot produce a valid response (cache miss in saved mode,
    or repeated failures in live mode).  Every caller must have a fallback."""


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(model: str, messages: list[dict], schema_name: str) -> str:
    """SHA-256 of (model, messages, schema name)."""
    payload = json.dumps({"model": model, "messages": messages, "schema": schema_name}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> str | None:
    path = _cache_path(key)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _write_cache(key: str, content: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log_llm_call(
    *,
    step: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: int,
    ok: bool,
    run_id: UUID | None,
) -> None:
    """Best-effort insert into llm_calls.  Failures are logged, never raised."""
    try:
        from app.services.supabase_client import get_supabase

        row = {
            "step": step,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "ok": ok,
        }
        if run_id is not None:
            row["run_id"] = str(run_id)

        get_supabase().table("llm_calls").insert(row).execute()
    except Exception:
        logger.warning("Failed to log llm_call for step=%s", step, exc_info=True)


# ---------------------------------------------------------------------------
# Groq HTTP helper
# ---------------------------------------------------------------------------

def _groq_client(settings: Settings, timeout: float = 60) -> httpx.AsyncClient:
    """Authenticated async client for the Groq completions API."""
    if not settings.groq_api_key:
        raise ServiceNotConfigured("Groq is not configured")
    return httpx.AsyncClient(
        base_url=GROQ_BASE_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        timeout=timeout,
    )


async def _call_groq(
    client: httpx.AsyncClient,
    *,
    model: str,
    messages: list[dict],
    schema: type[BaseModel],
) -> httpx.Response:
    """POST /chat/completions with structured JSON output. Handles 429 retries."""
    body = {
        "model": model,
        "messages": messages,
        "temperature": TEMPERATURE,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        response = await client.post("/chat/completions", json=body)
        if response.status_code != 429:
            return response
        # Rate-limited → wait and retry
        retry_after = min(
            float(response.headers.get("retry-after", "2")),
            MAX_RETRY_WAIT,
        )
        logger.info("Groq 429 on attempt %d, waiting %.1fs", attempt, retry_after)
        await asyncio.sleep(retry_after)

    # All attempts got 429
    return response  # type: ignore[possibly-undefined]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def complete_json(
    step: str,
    messages: list[dict],
    schema: type[T],
    run_id: UUID | None,
    *,
    settings: Settings | None = None,
) -> T:
    """Call the LLM and return a validated Pydantic model.

    In "saved" mode the cache is checked first and no HTTP call is made.
    In "live" mode the result is validated, retried once on schema errors,
    cached on success, and logged to the llm_calls table.

    Raises LLMUnavailable when the model cannot produce a valid result.
    """
    settings = settings or get_settings()
    model = settings.groq_model
    key = _cache_key(model, messages, schema.__name__)

    # ── Saved mode ──────────────────────────────────────────────────────
    if settings.llm_mode == "saved":
        cached = _read_cache(key)
        if cached is None:
            raise LLMUnavailable(f"No cached response for step={step}, schema={schema.__name__}")
        return schema.model_validate_json(cached)

    # ── Live mode ───────────────────────────────────────────────────────
    async with _groq_client(settings) as client:
        current_messages = list(messages)  # mutable copy for potential retry

        for validation_attempt in range(2):  # at most one validation retry
            t0 = time.monotonic()
            response = await _call_groq(client, model=model, messages=current_messages, schema=schema)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if response.status_code != 200:
                _log_llm_call(
                    step=step, model=model,
                    input_tokens=None, output_tokens=None,
                    latency_ms=latency_ms, ok=False, run_id=run_id,
                )
                raise LLMUnavailable(
                    f"Groq returned {response.status_code} for step={step}"
                )

            data = response.json()
            usage = data.get("usage", {})
            content = data["choices"][0]["message"]["content"]

            # Try to validate
            try:
                result = schema.model_validate_json(content)
            except Exception as exc:
                _log_llm_call(
                    step=step, model=model,
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    latency_ms=latency_ms, ok=False, run_id=run_id,
                )
                if validation_attempt == 0:
                    # Retry once: add the error to messages
                    logger.warning("Validation failed for step=%s, retrying: %s", step, exc)
                    current_messages = list(messages) + [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                f"Your previous response failed validation: {exc}\n"
                                "Please fix the errors and return valid JSON."
                            ),
                        },
                    ]
                    continue
                # Second failure
                raise LLMUnavailable(
                    f"Validation failed twice for step={step}: {exc}"
                ) from exc

            # Success
            _log_llm_call(
                step=step, model=model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                latency_ms=latency_ms, ok=True, run_id=run_id,
            )
            _write_cache(key, content)
            return result

    # Should never reach here, but satisfy the type checker
    raise LLMUnavailable(f"Unexpected state in complete_json for step={step}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Health check (preserved from the original module)
# ---------------------------------------------------------------------------

def groq_client(settings: Settings, timeout: float = 60) -> httpx.AsyncClient:
    """Public alias kept for check_groq and any other callers."""
    return _groq_client(settings, timeout)


async def check_groq(settings: Settings) -> str:
    """Lists models rather than generating text, so it spends no completion tokens."""
    if not settings.groq_api_key:
        return "not_configured"
    try:
        async with _groq_client(settings, timeout=5) as client:
            response = await client.get("/models")
        response.raise_for_status()
        return "ok"
    except httpx.HTTPError as exc:
        logger.warning("Groq check failed: %s", type(exc).__name__)
        return "error"
