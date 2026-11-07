import logging
from functools import lru_cache

import httpx
from supabase import Client, create_client

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured

logger = logging.getLogger(__name__)


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_key):
        raise ServiceNotConfigured("Supabase is not configured")
    return create_client(settings.supabase_url, settings.supabase_service_key)


async def check_supabase(settings: Settings) -> str:
    if not (settings.supabase_url and settings.supabase_service_key):
        return "not_configured"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/health",
                headers={"apikey": settings.supabase_service_key},
            )
        response.raise_for_status()
        return "ok"
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.warning("Supabase check failed: %s", type(exc).__name__)
        return "error"
