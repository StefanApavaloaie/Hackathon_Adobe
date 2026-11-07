# Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from conftest import FRONTEND


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


def test_live_stripe_key_is_rejected(make_settings):
    with pytest.raises(ValidationError, match="sk_test_"):
        make_settings(stripe_secret_key="sk_live_abc")


def test_rejected_stripe_key_is_not_printed_in_the_error(make_settings):
    with pytest.raises(ValidationError) as error:
        make_settings(stripe_secret_key="sk_live_abc")
    assert "sk_live_abc" not in str(error.value)


def test_test_stripe_key_is_accepted(make_settings):
    assert make_settings(stripe_secret_key="sk_test_abc").stripe_secret_key == "sk_test_abc"


def test_llm_mode_defaults_to_saved_so_tokens_are_not_spent_by_accident(make_settings):
    assert make_settings().llm_mode == "saved"


def test_dev_login_is_off_unless_explicitly_allowed(make_settings):
    assert make_settings().allow_dev_auth is False


def test_public_urls_ignore_trailing_slashes(make_settings):
    settings = make_settings(frontend_origin=f"{FRONTEND}/", public_api_url="http://127.0.0.1:8000/")
    assert settings.frontend_origin == FRONTEND
    assert settings.public_api_url == "http://127.0.0.1:8000"


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


def test_unhandled_errors_return_json_with_cors_headers(make_settings):
    app = create_app(make_settings())

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail")

    response = TestClient(app).get("/boom", headers={"Origin": FRONTEND})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["access-control-allow-origin"] == FRONTEND
