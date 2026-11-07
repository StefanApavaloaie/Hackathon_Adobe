# Owned by feature/delivery.
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.delivery.send import get_delivery_store
from app.metrics import CampaignMetrics, aggregate, compute_metrics, get_metrics_store

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
PAST = (NOW - timedelta(minutes=5)).isoformat()
FUTURE = (NOW + timedelta(seconds=30)).isoformat()
CAMPAIGN = uuid.UUID("11111111-1111-1111-1111-111111111111")
COHORT = "cccccccc-0000-4000-8000-000000000001"
VAR_A = "aaaaaaaa-0000-4000-8000-00000000000a"
VAR_B = "bbbbbbbb-0000-4000-8000-00000000000b"


def recipient(rid, source="live", variant=VAR_A, label="A"):
    return {"id": rid, "source": source, "variant_id": variant, "cohort_id": COHORT, "variant_label": label}


def event(rid, event_type, at=PAST):
    return {"recipient_id": rid, "type": event_type, "occurred_at": at}


def conversion(rid, mrr, at=PAST):
    return {"recipient_id": rid, "mrr_cents": mrr, "occurred_at": at}


def test_future_events_and_conversions_are_ignored():
    recipients = [recipient("r1", "simulated")]
    events = [event("r1", "clicked", FUTURE), event("r1", "page_viewed", FUTURE)]
    conversions = [conversion("r1", 4900, FUTURE)]
    metrics = aggregate(CAMPAIGN, recipients, events, conversions, NOW)
    assert metrics.simulated.clicks == 0
    assert metrics.simulated.page_views == 0
    assert metrics.simulated.conversions == 0
    assert metrics.simulated.mrr_recovered_cents == 0


def test_live_and_simulated_are_counted_separately():
    recipients = [recipient("live1"), recipient("sim1", "simulated"), recipient("sim2", "simulated")]
    events = [event("live1", "clicked"), event("sim1", "clicked"), event("sim2", "clicked")]
    conversions = [conversion("live1", 4410), conversion("sim1", 3675)]
    metrics = aggregate(CAMPAIGN, recipients, events, conversions, NOW)
    assert (metrics.live.recipients, metrics.live.clicks, metrics.live.conversions) == (1, 1, 1)
    assert (metrics.simulated.recipients, metrics.simulated.clicks, metrics.simulated.conversions) == (2, 2, 1)
    assert metrics.live.mrr_recovered_cents == 4410
    assert metrics.simulated.mrr_recovered_cents == 3675


def test_a_recipient_who_clicks_twice_counts_once():
    metrics = aggregate(
        CAMPAIGN,
        [recipient("r1")],
        [event("r1", "clicked"), event("r1", "clicked"), event("r1", "page_viewed"), event("r1", "page_viewed")],
        [],
        NOW,
    )
    assert metrics.live.clicks == 1
    assert metrics.live.page_views == 1


def test_revenue_adds_up_across_variants():
    recipients = [recipient("r1"), recipient("r2"), recipient("r3", variant=VAR_B, label="B")]
    conversions = [conversion("r1", 4410), conversion("r2", 3675), conversion("r3", 4900)]
    metrics = aggregate(CAMPAIGN, recipients, [], conversions, NOW)
    assert metrics.live.mrr_recovered_cents == 4410 + 3675 + 4900
    assert metrics.live.conversions == 3
    by_label = {v.variant_label: v for v in metrics.live.variants}
    assert by_label["A"].mrr_recovered_cents == 8085
    assert by_label["B"].mrr_recovered_cents == 4900


def test_breakdown_by_variant_counts_each_funnel_step():
    recipients = [recipient("r1"), recipient("r2"), recipient("r3", variant=VAR_B, label="B")]
    events = [
        event("r1", "clicked"), event("r1", "page_viewed"), event("r1", "checkout_started"),
        event("r2", "clicked"),
        event("r3", "page_viewed"),
    ]
    metrics = aggregate(CAMPAIGN, recipients, events, [conversion("r1", 4410)], NOW)
    [a, b] = metrics.live.variants
    assert (a.variant_label, a.recipients, a.clicks, a.page_views, a.checkouts_started, a.conversions) == ("A", 2, 2, 1, 1, 1)
    assert (b.variant_label, b.recipients, b.clicks, b.page_views, b.checkouts_started, b.conversions) == ("B", 1, 0, 1, 0, 0)
    assert str(a.cohort_id) == COHORT and str(a.variant_id) == VAR_A
    assert metrics.simulated.variants == []


def test_events_for_other_recipients_and_unknown_types_are_ignored():
    metrics = aggregate(CAMPAIGN, [recipient("r1")], [event("other", "clicked"), event("r1", "sent")], [], NOW)
    assert metrics.live.clicks == 0


def test_empty_campaign_is_all_zeros():
    metrics = aggregate(CAMPAIGN, [], [], [], NOW)
    assert metrics == CampaignMetrics(campaign_id=CAMPAIGN, live=metrics.live, simulated=metrics.simulated)
    assert metrics.live.recipients == 0 and metrics.simulated.variants == []


# --- compute_metrics and the results route, with fake stores -----------------


class FakeMetricsStore:
    def __init__(self):
        self.recipients = [recipient("r1"), recipient("s1", "simulated")]
        self.events = [event("r1", "clicked"), event("s1", "clicked", FUTURE)]
        self.conversions = [conversion("r1", 4410)]
        self.asked_until = None

    def get_recipients(self, campaign_id):
        return self.recipients

    def get_events(self, recipient_ids, until):
        self.asked_until = until
        return [e for e in self.events if e["recipient_id"] in recipient_ids]

    def get_conversions(self, recipient_ids, until):
        return [c for c in self.conversions if c["recipient_id"] in recipient_ids]


def test_compute_metrics_reads_the_store_and_ignores_the_future():
    store = FakeMetricsStore()
    metrics = compute_metrics(CAMPAIGN, store=store, now=NOW)
    assert metrics.live.clicks == 1 and metrics.live.mrr_recovered_cents == 4410
    assert metrics.simulated.clicks == 0
    assert store.asked_until == NOW


class FakeCampaigns:
    def __init__(self, status="sent"):
        self.status = status

    def get_campaign(self, campaign_id):
        return {"id": campaign_id, "status": self.status} if campaign_id == str(CAMPAIGN) else None


@pytest.fixture
def http(client):
    client.app.dependency_overrides[get_delivery_store] = lambda: FakeCampaigns()
    client.app.dependency_overrides[get_metrics_store] = lambda: FakeMetricsStore()
    return client


def test_results_route_returns_status_and_separate_live_and_simulated(http):
    response = http.get(f"/api/campaigns/{CAMPAIGN}/results")
    assert response.status_code == 200
    body = response.json()
    assert body["campaign_id"] == str(CAMPAIGN)
    assert body["status"] == "sent"
    assert body["metrics"]["live"]["conversions"] == 1
    assert body["metrics"]["live"]["mrr_recovered_cents"] == 4410
    assert body["metrics"]["simulated"]["recipients"] == 1
    assert "total" not in body["metrics"]


def test_results_for_unknown_campaign_returns_404(http):
    assert http.get(f"/api/campaigns/{uuid.uuid4()}/results").status_code == 404


def test_results_need_login(make_settings, client):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings = make_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    assert TestClient(app).get(f"/api/campaigns/{CAMPAIGN}/results").status_code == 401
