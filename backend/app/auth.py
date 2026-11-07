# Owned by feature/delivery. Keep the names and return type: protected routes in both branches use them.
from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured

SUPABASE_TIMEOUT_SECONDS = 5.0


class AuthUser(BaseModel):
    id: str
    email: str | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def bearer_token(authorization: str | None) -> str | None:
    """Returns the token from an 'Authorization: Bearer <token>' header, or None."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def get_auth_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """The HTTP client used to ask Supabase about a token. Tests override it."""
    async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT_SECONDS) as client:
        yield client


async def require_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    http: httpx.AsyncClient = Depends(get_auth_http_client),
) -> AuthUser:
    """Checks the Supabase login token sent by the dashboard.

    ALLOW_DEV_AUTH=true skips the check for local development. Render never sets it.
    """
    if settings.allow_dev_auth:
        return AuthUser(id="dev-user")

    token = bearer_token(request.headers.get("authorization"))
    if token is None:
        raise _unauthorized("Not logged in")

    if not settings.supabase_url or not settings.supabase_service_key:
        raise ServiceNotConfigured("Login is not configured: set SUPABASE_URL and SUPABASE_SERVICE_KEY")

    try:
        response = await http.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_service_key, "Authorization": f"Bearer {token}"},
            timeout=SUPABASE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login check is unavailable") from exc

    if response.status_code != status.HTTP_200_OK:
        raise _unauthorized("Login token is invalid or expired")

    user = response.json()
    if not isinstance(user, dict) or not user.get("id"):
        raise _unauthorized("Login token is invalid or expired")
    return AuthUser(id=str(user["id"]), email=user.get("email"))
