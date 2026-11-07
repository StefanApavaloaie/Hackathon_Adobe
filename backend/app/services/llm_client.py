import logging

import httpx

from app.config import Settings
from app.errors import ServiceNotConfigured

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def groq_client(settings: Settings, timeout: float = 60) -> httpx.AsyncClient:
    """Authenticated client. Completions must respect settings.llm_mode when added."""
    if not settings.groq_api_key:
        raise ServiceNotConfigured("Groq is not configured")
    return httpx.AsyncClient(
        base_url=GROQ_BASE_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        timeout=timeout,
    )


async def check_groq(settings: Settings) -> str:
    """Lists models rather than generating text, so it spends no completion tokens."""
    if not settings.groq_api_key:
        return "not_configured"
    try:
        async with groq_client(settings, timeout=5) as client:
            response = await client.get("/models")
        response.raise_for_status()
        return "ok"
    except httpx.HTTPError as exc:
        logger.warning("Groq check failed: %s", type(exc).__name__)
        return "error"
