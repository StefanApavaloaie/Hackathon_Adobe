# Owned by feature/delivery.
import hashlib
import hmac
import json
import time

import pytest

from app.config import get_settings
from app.routers.webhooks import get_webhook_store

SECRET = "whsec_test_secret"
RECIPIENT = "0b1a2c3d-0000-4000-8000-000000000001"


def signed(payload: str, secret: str = SECRET, timestamp: int | None = None) -> dict:
    timestamp = timestamp or int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={signature}", "Content-Type": "application/json"}


def checkout_event(event_id="evt_1", recipient_id=RECIPIENT, session_id="cs_test_1", amount_total=3675,
                   event_type="checkout.session.completed", payment_status="paid"):
    metadata = {"recipient_id": recipient_id, "campaign_id": "c1", "variant_id": "v1"} if recipient_id else {}
    return json.dumps({
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {"object": {
            "id": session_id,
            "object": "checkout.session",
            "amount_total": amount_total,
            "payment_status": payment_status,
            "metadata": metadata,
        }},
    })


class FakeWebhookStore:
    def __init__(self, recipients=None):
        self.processed: set[tuple[str, str]] = set()
        self.conversions: dict[str, dict] = {}
        self.recipients = recipients if recipients is not None else {RECIPIENT: {"id": RECIPIENT, "source": "live"}}
        self.fail_conversion = False

    def is_processed(self, provider, event_id):
        return (provider, event_id) in self.processed

    def mark_processed(self, provider, event_id):
        self.processed.add((provider, event_id))

    def get_recipient(self, recipient_id):
        return self.recipients.get(recipient_id)

    def add_conversion(self, row):
        if self.fail_conversion:
            raise RuntimeError("database down")
        self.conversions.setdefault(row["recipient_id"], row)


@pytest.fixture
def store():
    return FakeWebhookStore()


@pytest.fixture
def http(client, store):
    settings = client.app.dependency_overrides[get_settings]().model_copy(update={"stripe_webhook_secret": SECRET})
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[get_webhook_store] = lambda: store
    return client


def post(http, payload, headers=None):
    return http.post("/webhooks/stripe", content=payload, headers=headers if headers is not None else signed(payload))


def test_bad_signature_returns_400(http, store):
    payload = checkout_event()
    assert post(http, payload, signed(payload, secret="whsec_wrong")).status_code == 400
    assert store.conversions == {}


def test_missing_signature_returns_400(http):
    assert post(http, checkout_event(), {"Content-Type": "application/json"}).status_code == 400


def test_tampered_body_returns_400(http, store):
    headers = signed(checkout_event(amount_total=3675))
    assert post(http, checkout_event(amount_total=1), headers).status_code == 400
    assert store.conversions == {}


def test_old_signature_returns_400(http):
    payload = checkout_event()
    assert post(http, payload, signed(payload, timestamp=int(time.time()) - 3600)).status_code == 400


def test_completed_checkout_creates_one_live_conversion(http, store):
    assert post(http, checkout_event()).status_code == 200
    assert store.conversions == {
        RECIPIENT: {"recipient_id": RECIPIENT, "stripe_session_id": "cs_test_1", "mrr_cents": 3675, "source": "live"}
    }
    assert ("stripe", "evt_1") in store.processed


def test_duplicate_event_adds_nothing(http, store):
    post(http, checkout_event())
    store.conversions.clear()
    response = post(http, checkout_event())
    assert response.status_code == 200
    assert store.conversions == {}


def test_failed_save_is_not_marked_processed_so_stripe_can_retry(http, store):
    store.fail_conversion = True
    assert post(http, checkout_event()).status_code == 500
    assert store.processed == set()
    store.fail_conversion = False
    assert post(http, checkout_event()).status_code == 200
    assert RECIPIENT in store.conversions


def test_other_event_types_are_acknowledged_and_ignored(http, store):
    assert post(http, checkout_event(event_type="customer.created")).status_code == 200
    assert store.conversions == {}


@pytest.mark.parametrize("recipient_id", [None, "not-a-uuid", "0b1a2c3d-0000-4000-8000-00000000ffff"])
def test_checkout_without_a_known_recipient_is_ignored(http, store, recipient_id):
    assert post(http, checkout_event(recipient_id=recipient_id)).status_code == 200
    assert store.conversions == {}


def test_unpaid_checkout_is_ignored(http, store):
    assert post(http, checkout_event(payment_status="unpaid")).status_code == 200
    assert store.conversions == {}


def test_checkout_for_a_simulated_recipient_is_not_counted_as_live(client):
    store = FakeWebhookStore(recipients={RECIPIENT: {"id": RECIPIENT, "source": "simulated"}})
    settings = client.app.dependency_overrides[get_settings]().model_copy(update={"stripe_webhook_secret": SECRET})
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[get_webhook_store] = lambda: store
    assert post(client, checkout_event()).status_code == 200
    assert store.conversions == {}


def test_missing_webhook_secret_returns_503(client, store):
    client.app.dependency_overrides[get_webhook_store] = lambda: store
    assert post(client, checkout_event()).status_code == 503
