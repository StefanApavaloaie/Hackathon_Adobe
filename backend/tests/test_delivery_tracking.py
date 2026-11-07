# Owned by feature/delivery.
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.routers.tracking import get_tracking_store

FRONTEND = "http://localhost:5173"
TOKEN = "AbC_-123xyzAbC_-123xyz"


class FakeTrackingStore:
    def __init__(self, source="live"):
        self.recipients = {TOKEN: {"id": "r1", "customer_id": "cus1", "source": source}}
        self.unsubscribed_at: dict[str, datetime] = {}
        self.events: list[tuple] = []
        self.lookups = 0

    def get_recipient(self, token):
        self.lookups += 1
        return self.recipients.get(token)

    def add_event(self, recipient_id, event_type, source):
        self.events.append((recipient_id, event_type, source))

    def unsubscribe_customer(self, customer_id, at):
        if customer_id in self.unsubscribed_at:
            return False
        self.unsubscribed_at[customer_id] = at
        return True


@pytest.fixture
def store():
    return FakeTrackingStore()


@pytest.fixture
def http(client, store) -> TestClient:
    client.app.dependency_overrides[get_tracking_store] = lambda: store
    return TestClient(client.app, follow_redirects=False)


def test_click_redirects_to_the_page_for_the_token(http):
    response = http.get(f"/r/{TOKEN}")
    assert response.status_code == 302
    assert response.headers["location"] == f"{FRONTEND}/w/{TOKEN}"


def test_click_records_an_event_with_the_recipients_source(http, store):
    http.get(f"/r/{TOKEN}")
    assert store.events == [("r1", "clicked", "live")]


def test_click_from_a_simulated_recipient_is_recorded_as_simulated(client):
    store = FakeTrackingStore(source="simulated")
    client.app.dependency_overrides[get_tracking_store] = lambda: store
    TestClient(client.app, follow_redirects=False).get(f"/r/{TOKEN}")
    assert store.events == [("r1", "clicked", "simulated")]


def test_click_with_an_unknown_token_returns_404(http, store):
    assert http.get("/r/unknownTokenUnknownTok").status_code == 404
    assert store.events == []


def test_malformed_tokens_are_rejected_without_a_lookup(http, store):
    for token in ("a" * 200, "bad%20token", "x"):
        assert http.get(f"/r/{token}").status_code == 404
    assert store.lookups == 0


def test_unsubscribe_sets_unsubscribed_at_and_records_an_event(http, store):
    response = http.get(f"/u/{TOKEN}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "unsubscribed" in response.text.lower()
    assert "cus1" in store.unsubscribed_at
    assert store.events == [("r1", "unsubscribed", "live")]


def test_unsubscribing_twice_records_one_event(http, store):
    http.get(f"/u/{TOKEN}")
    assert http.get(f"/u/{TOKEN}").status_code == 200
    assert store.events == [("r1", "unsubscribed", "live")]


def test_one_click_unsubscribe_by_post_works(http, store):
    response = http.post(f"/u/{TOKEN}", data={"List-Unsubscribe": "One-Click"})
    assert response.status_code == 200
    assert "cus1" in store.unsubscribed_at


def test_unsubscribe_with_an_unknown_token_returns_404(http, store):
    response = http.get("/u/unknownTokenUnknownTok")
    assert response.status_code == 404
    assert store.unsubscribed_at == {}
