# Owned by feature/delivery.
import asyncio
import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import AuthUser, get_auth_http_client, require_user
from app.config import get_settings
from app.main import create_app

SUPABASE_URL = "https://project.supabase.co"
SERVICE_KEY = "service-key"
PROTECTED = "/_test/protected"


def add_protected_route(app) -> None:
    """A route that only needs login, so these tests don't depend on any real route."""

    @app.get(PROTECTED, dependencies=[Depends(require_user)])
    def protected() -> dict:
        return {"ok": True}


def supabase_stub(calls: list[httpx.Request]):
    """Accepts only the token 'good-token', like Supabase's /auth/v1/user."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.headers.get("authorization") == "Bearer good-token":
            return httpx.Response(200, json={"id": "user-123", "email": "marketer@example.com"})
        return httpx.Response(401, json={"msg": "invalid JWT"})

    return handler


@pytest.fixture
def calls() -> list[httpx.Request]:
    return []


@pytest.fixture
def make_client(make_settings, calls):
    def factory(**overrides) -> TestClient:
        overrides.setdefault("supabase_url", SUPABASE_URL)
        overrides.setdefault("supabase_service_key", SERVICE_KEY)
        settings = make_settings(**overrides)
        app = create_app(settings)
        add_protected_route(app)
        app.dependency_overrides[get_settings] = lambda: settings

        async def mock_http_client():
            async with httpx.AsyncClient(transport=httpx.MockTransport(supabase_stub(calls))) as http:
                yield http

        app.dependency_overrides[get_auth_http_client] = mock_http_client
        return TestClient(app)

    return factory


def test_missing_token_returns_401(make_client, calls):
    response = make_client().get(PROTECTED)
    assert response.status_code == 401
    assert calls == []


def test_non_bearer_header_returns_401(make_client, calls):
    response = make_client().get(PROTECTED, headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
    assert calls == []


def test_rejected_token_returns_401(make_client):
    response = make_client().get(PROTECTED, headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


def test_valid_token_reaches_the_route_and_asks_supabase_correctly(make_client, calls):
    response = make_client().get(PROTECTED, headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 200
    [request] = calls
    assert str(request.url) == f"{SUPABASE_URL}/auth/v1/user"
    assert request.headers["apikey"] == SERVICE_KEY


def test_valid_token_returns_the_user(make_settings, calls):
    settings = make_settings(supabase_url=SUPABASE_URL, supabase_service_key=SERVICE_KEY)
    request = Request({"type": "http", "headers": [(b"authorization", b"Bearer good-token")]})

    async def check() -> AuthUser:
        async with httpx.AsyncClient(transport=httpx.MockTransport(supabase_stub(calls))) as http:
            return await require_user(request, settings, http)

    user = asyncio.run(check())
    assert user.id == "user-123"
    assert user.email == "marketer@example.com"


def test_dev_bypass_works_when_allowed(make_client, calls):
    response = make_client(allow_dev_auth=True).get(PROTECTED)
    assert response.status_code == 200
    assert calls == []


def test_dev_bypass_is_off_by_default(make_client):
    assert make_client().get(PROTECTED).status_code == 401


def test_unconfigured_supabase_returns_503(make_client):
    response = make_client(supabase_url="").get(PROTECTED, headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 503


def test_supabase_unreachable_returns_503(make_settings):
    settings = make_settings(supabase_url=SUPABASE_URL, supabase_service_key=SERVICE_KEY)
    app = create_app(settings)
    add_protected_route(app)
    app.dependency_overrides[get_settings] = lambda: settings

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    async def broken_http_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as http:
            yield http

    app.dependency_overrides[get_auth_http_client] = broken_http_client
    response = TestClient(app).get(PROTECTED, headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 503
