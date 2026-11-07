# Owned by feature/delivery.
import pytest
from fastapi.testclient import TestClient

from app.routers.pages import PRICE_LOOKUP_KEY, get_page_store, get_stripe_client

FRONTEND = "http://localhost:5173"
TOKEN = "AbC_-123xyzAbC_-123xyz"

PAGE_CONTENT = {
    "headline": "Pro, for less",
    "subheadline": "25% off for 3 months.",
    "reasons": [{"title": "Everything you had", "body": "Ready to pick up again."}],
    "objection_response": "Cancel any time.",
    "cta_label": "Come back for less",
}


def page_data(percent_off=25, coupon="winback_25pct_3m", page_content=None, source="live"):
    return {
        "recipient": {"id": "r1", "campaign_id": "camp1", "variant_id": "var1", "source": source},
        "customer": {
            "name": "Ana Popescu",
            "email": "ana@team.dev",
            "stripe_customer_id": "cus_123",
            "cancel_comment": "Too expensive",
            "mrr_cents": 4900,
        },
        "page_content": page_content if page_content is not None else PAGE_CONTENT,
        "offer": {
            "id": "offer1",
            "label": f"{percent_off}% off for 3 months",
            "percent_off": percent_off,
            "duration_months": 3,
            "stripe_coupon_id": coupon,
        },
    }


class FakePageStore:
    def __init__(self, data=None):
        self.data = {TOKEN: data or page_data()}
        self.events = []

    def get_page_data(self, token):
        return self.data.get(token)

    def add_event(self, recipient_id, event_type, source):
        self.events.append((recipient_id, event_type, source))


class FakeStripe:
    def __init__(self):
        stripe = self
        self.sessions = []

        class Prices:
            def list(self, params):
                assert params["lookup_keys"] == [PRICE_LOOKUP_KEY]
                return type("L", (), {"data": [type("P", (), {"id": "price_pro"})()]})()

        class Sessions:
            def create(self, params):
                stripe.sessions.append(params)
                return type("S", (), {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"})()

        self.v1 = type("V1", (), {"prices": Prices(), "checkout": type("C", (), {"sessions": Sessions()})()})()


@pytest.fixture
def store():
    return FakePageStore()


@pytest.fixture
def stripe():
    return FakeStripe()


@pytest.fixture
def http(client, store, stripe) -> TestClient:
    client.app.dependency_overrides[get_page_store] = lambda: store
    client.app.dependency_overrides[get_stripe_client] = lambda: stripe
    return client


# --- GET /api/pages/{token} -------------------------------------------------


def test_page_returns_only_content_offer_and_first_name(http):
    response = http.get(f"/api/pages/{TOKEN}")
    assert response.status_code == 200
    assert response.json() == {
        "page_content": PAGE_CONTENT,
        "offer": {"label": "25% off for 3 months", "percent_off": 25, "duration_months": 3},
        "first_name": "Ana",
    }


def test_page_response_leaks_no_other_customer_data(http):
    text = http.get(f"/api/pages/{TOKEN}").text
    for secret in ("ana@team.dev", "cus_123", "Popescu", "Too expensive", "4900", "winback_25pct_3m", "r1", "camp1"):
        assert secret not in text


def test_page_view_is_recorded_with_the_recipients_source(http, store):
    http.get(f"/api/pages/{TOKEN}")
    assert store.events == [("r1", "page_viewed", "live")]


def test_page_with_unknown_token_returns_404(http, store):
    assert http.get("/api/pages/unknownTokenUnknownTok").status_code == 404
    assert http.get("/api/pages/bad").status_code == 404
    assert store.events == []


def test_invalid_page_content_falls_back_to_default_copy(client, stripe):
    store = FakePageStore(page_data(page_content={"headline": "only a headline"}))
    client.app.dependency_overrides[get_page_store] = lambda: store
    body = client.get(f"/api/pages/{TOKEN}").json()
    assert set(body["page_content"]) == set(PAGE_CONTENT)
    assert body["page_content"]["headline"]


# --- POST /api/pages/{token}/checkout ---------------------------------------


def test_checkout_creates_a_subscription_session_with_the_stored_offer(http, stripe, store):
    response = http.post(f"/api/pages/{TOKEN}/checkout")
    assert response.status_code == 200
    assert response.json() == {"url": "https://checkout.stripe.com/c/pay/cs_test_1"}
    [params] = stripe.sessions
    assert params["mode"] == "subscription"
    assert params["customer"] == "cus_123"
    assert params["line_items"] == [{"price": "price_pro", "quantity": 1}]
    assert params["discounts"] == [{"coupon": "winback_25pct_3m"}]
    assert params["success_url"] == f"{FRONTEND}/thanks"
    assert params["cancel_url"] == f"{FRONTEND}/w/{TOKEN}"
    assert params["metadata"] == {"recipient_id": "r1", "campaign_id": "camp1", "variant_id": "var1"}
    assert store.events == [("r1", "checkout_started", "live")]


def test_checkout_ignores_an_offer_sent_by_the_browser(http, stripe):
    http.post(
        f"/api/pages/{TOKEN}/checkout",
        json={"coupon": "FREE100", "percent_off": 100, "price": "price_cheap", "discounts": [{"coupon": "FREE100"}]},
    )
    [params] = stripe.sessions
    assert params["discounts"] == [{"coupon": "winback_25pct_3m"}]
    assert params["line_items"] == [{"price": "price_pro", "quantity": 1}]


def test_checkout_without_a_discount_has_no_coupon(client, stripe):
    store = FakePageStore(page_data(percent_off=0, coupon=None))
    client.app.dependency_overrides[get_page_store] = lambda: store
    client.app.dependency_overrides[get_stripe_client] = lambda: stripe
    assert client.post(f"/api/pages/{TOKEN}/checkout").status_code == 200
    assert "discounts" not in stripe.sessions[0]


def test_checkout_refuses_a_discounted_offer_whose_coupon_is_missing(client, stripe):
    store = FakePageStore(page_data(percent_off=25, coupon=None))
    client.app.dependency_overrides[get_page_store] = lambda: store
    client.app.dependency_overrides[get_stripe_client] = lambda: stripe
    assert client.post(f"/api/pages/{TOKEN}/checkout").status_code == 503
    assert stripe.sessions == []


def test_checkout_with_unknown_token_returns_404(http, stripe):
    assert http.post("/api/pages/unknownTokenUnknownTok/checkout").status_code == 404
    assert stripe.sessions == []
