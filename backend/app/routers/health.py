import asyncio

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.llm_client import check_groq
from app.services.supabase_client import check_supabase

router = APIRouter(tags=["health"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health() -> dict[str, str]:
    """Liveness only. Makes no outside calls, so the keep-awake ping stays cheap."""
    return {"status": "ok"}


@router.get("/health/dependencies")
async def dependencies(settings: Settings = Depends(get_settings)) -> dict:
    """Reports status words only, never keys or error details."""
    supabase, groq = await asyncio.gather(check_supabase(settings), check_groq(settings))
    results = {
        "supabase": supabase,
        "groq": groq,
        "stripe": "configured" if settings.stripe_secret_key else "not_configured",
        "resend": "configured" if settings.resend_api_key else "not_configured",
    }
    healthy = all(value in ("ok", "configured") for value in results.values())
    return {"status": "ok" if healthy else "degraded", "dependencies": results}
