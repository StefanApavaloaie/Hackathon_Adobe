import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import create_app

FRONTEND = "http://localhost:5173"
RUN_ID = str(uuid.uuid4())
CAMPAIGN_ID = str(uuid.uuid4())

STUBBED_ROUTES = [
    ("POST", "/api/runs"),
    ("GET", f"/api/runs/{RUN_ID}"),
    ("POST", f"/api/runs/{RUN_ID}/resume"),
    ("GET", f"/api/campaigns/{CAMPAIGN_ID}"),
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/approve"),
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/reject"),
    ("GET", f"/api/campaigns/{CAMPAIGN_ID}/results"),
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/report"),
    ("GET", "/api/usage"),
    ("GET", "/r/some-token"),
    ("GET", "/api/pages/some-token"),
    ("POST", "/api/pages/some-token/checkout"),
    ("GET", "/u/some-token"),
    ("POST", "/webhooks/stripe"),
    ("POST", "/webhooks/resend"),
]


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, frontend_origin=FRONTEND, **overrides)


@pytest.fixture
def client() -> TestClient:
    settings = make_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_supports_head_for_uptime_pingers(client):
    assert client.head("/health").status_code == 200


def test_dependencies_report_not_configured_without_keys(client):
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "supabase": "not_configured",
            "groq": "not_configured",
            "stripe": "not_configured",
            "resend": "not_configured",
        },
    }


@pytest.mark.parametrize("method,path", STUBBED_ROUTES)
def test_section_7_routes_are_stubbed(client, method, path):
    assert client.request(method, path).status_code == 501


def test_live_stripe_key_is_rejected():
    with pytest.raises(ValidationError, match="sk_test_"):
        make_settings(stripe_secret_key="sk_live_abc")


def test_rejected_stripe_key_is_not_printed_in_the_error():
    with pytest.raises(ValidationError) as error:
        make_settings(stripe_secret_key="sk_live_abc")
    assert "sk_live_abc" not in str(error.value)


def test_test_stripe_key_is_accepted():
    assert make_settings(stripe_secret_key="sk_test_abc").stripe_secret_key == "sk_test_abc"


def test_llm_mode_defaults_to_saved_so_tokens_are_not_spent_by_accident():
    assert make_settings().llm_mode == "saved"


def test_cors_allows_the_frontend_origin(client):
    response = client.get("/health", headers={"Origin": FRONTEND})
    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_cors_ignores_a_trailing_slash_in_the_configured_origin():
    app = create_app(Settings(_env_file=None, frontend_origin=f"{FRONTEND}/"))
    response = TestClient(app).get("/health", headers={"Origin": FRONTEND})
    assert response.headers["access-control-allow-origin"] == FRONTEND


def test_cors_rejects_other_origins(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_unhandled_errors_return_json_with_cors_headers():
    app = create_app(make_settings())

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail")

    response = TestClient(app).get("/boom", headers={"Origin": FRONTEND})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["access-control-allow-origin"] == FRONTEND
