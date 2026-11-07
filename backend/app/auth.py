# Owned by feature/delivery. Keep the names and return type: protected routes in both branches use them.
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from app.config import Settings, get_settings


class AuthUser(BaseModel):
    id: str
    email: str | None = None


async def require_user(settings: Settings = Depends(get_settings)) -> AuthUser:
    """PLACEHOLDER. Replace the body with a real Supabase login check.

    Until then, requests pass only when ALLOW_DEV_AUTH=true, so a deployment
    without it blocks protected routes instead of leaving them open.
    """
    if not settings.allow_dev_auth:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login is not implemented yet")
    return AuthUser(id="dev-user")
