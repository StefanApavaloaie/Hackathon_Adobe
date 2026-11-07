# Owned by feature/delivery. Delete each route or placeholder as you build it, then delete this file.
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.metrics import compute_metrics
from app.stripe_import import import_customers

CAMPAIGN_ID = str(uuid.uuid4())

DELIVERY_STUBS = [
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/approve"),
    #("GET", f"/api/campaigns/{CAMPAIGN_ID}/results"),
    ("GET", "/r/some-token"),
    ("GET", "/api/pages/some-token"),
    ("POST", "/api/pages/some-token/checkout"),
    ("GET", "/u/some-token"),
    ("POST", "/webhooks/stripe"),
    ("POST", "/webhooks/resend"),
]


@pytest.mark.parametrize("method,path", DELIVERY_STUBS)
def test_delivery_routes_are_stubbed(client, method, path):
    assert client.request(method, path).status_code == 501


def test_import_placeholder_imports_nothing():
    assert import_customers() == 0


def test_metrics_placeholder_returns_zeros_for_both_sources():
    metrics = compute_metrics(uuid.UUID(CAMPAIGN_ID))
    assert str(metrics.campaign_id) == CAMPAIGN_ID
    assert metrics.live.conversions == 0
    assert metrics.simulated.conversions == 0
    assert metrics.live.variants == []


def test_placeholder_login_blocks_protected_routes_unless_dev_login_is_allowed(make_settings):
    app = create_app(make_settings())
    response = TestClient(app).get(f"/api/campaigns/{CAMPAIGN_ID}/results")
    assert response.status_code == 503
    assert response.json() == {"detail": "Login is not implemented yet"}


def test_public_routes_need_no_login(make_settings):
    app = create_app(make_settings())
    assert TestClient(app).get("/api/pages/some-token").status_code == 501
