import random
import uuid
from datetime import datetime, timedelta, timezone

from app import simulator
from app.simulator import HIDDEN_RATES, plan_outcomes, simulate_responses

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
OFFERS = {"off-50": {"percent_off": 50, "duration_months": 1}, "off-0": {"percent_off": 0, "duration_months": 1}}


def _recipients(n, source="simulated", feedback="too_expensive", offer_id="off-50"):
    return [
        {"recipient_id": f"r-{source}-{i}", "source": source, "cancel_feedback": feedback, "mrr_cents": 1000, "offer_id": offer_id}
        for i in range(n)
    ]


def test_same_seed_gives_same_outcomes():
    recs = _recipients(30)
    a = plan_outcomes(recs, OFFERS, random.Random("seed"), now=NOW)
    b = plan_outcomes(recs, OFFERS, random.Random("seed"), now=NOW)
    assert a == b
    assert a[0], "expected some events with a 60% click rate over 30 recipients"


def test_zero_click_rate_gives_no_events():
    zero = {k: {band: (0.0, 1.0) for band in v} for k, v in HIDDEN_RATES.items()}
    events, conversions = plan_outcomes(_recipients(50), OFFERS, random.Random("x"), now=NOW, rates=zero)
    assert events == [] and conversions == []


def test_every_timestamp_within_60_seconds():
    events, conversions = plan_outcomes(_recipients(200), OFFERS, random.Random("t"), now=NOW)
    assert events and conversions
    for row in events + conversions:
        offset = datetime.fromisoformat(row["occurred_at"]) - NOW
        assert timedelta(0) <= offset <= timedelta(seconds=60)


def test_only_simulated_recipients_are_used():
    always = {k: {band: (1.0, 1.0) for band in v} for k, v in HIDDEN_RATES.items()}
    recs = _recipients(5, source="live") + _recipients(5)
    events, conversions = plan_outcomes(recs, OFFERS, random.Random("s"), now=NOW, rates=always)
    ids = {e["recipient_id"] for e in events} | {c["recipient_id"] for c in conversions}
    assert ids == {f"r-simulated-{i}" for i in range(5)}
    assert all(e["source"] == "simulated" for e in events)


def test_conversion_mrr_is_discounted_price():
    always = {k: {band: (1.0, 1.0) for band in v} for k, v in HIDDEN_RATES.items()}
    _, conversions = plan_outcomes(_recipients(1), OFFERS, random.Random("m"), now=NOW, rates=always)
    assert conversions[0]["mrr_cents"] == 500


# ---------------------------------------------------------------------------
# Database wrapper, against a tiny in-memory fake of the Supabase client
# ---------------------------------------------------------------------------
class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters, self.rows = db, table, [], None

    def select(self, _cols="*"):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        vals = set(vals)
        self.filters.append(lambda r: r.get(col) in vals)
        return self

    def insert(self, rows):
        self.rows = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        store = self.db.tables.setdefault(self.table, [])
        if self.rows is not None:
            store.extend(self.rows)
            return _Result(self.rows)
        return _Result([r for r in store if all(f(r) for f in self.filters)])


class FakeDB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query(self, name)


def _seeded_db(campaign_id):
    customers = [{"id": f"cust-{i}", "cancel_feedback": "too_expensive", "mrr_cents": 2000} for i in range(40)]
    recipients = [
        {"id": f"rec-{i}", "campaign_id": campaign_id, "customer_id": f"cust-{i}", "variant_id": "var-a",
         "source": "simulated" if i < 30 else "live"}
        for i in range(40)
    ]
    return FakeDB({
        "customers": customers,
        "recipients": recipients,
        "variants": [{"id": "var-a", "offer_id": "off-50"}],
        "offers": [{"id": "off-50", "percent_off": 50, "duration_months": 3}],
        "events": [],
        "conversions": [],
    })


def test_simulate_responses_writes_schema_rows_and_is_idempotent(monkeypatch):
    campaign_id = uuid.uuid4()
    db = _seeded_db(str(campaign_id))
    monkeypatch.setattr(simulator, "get_supabase", lambda: db)

    simulate_responses(campaign_id)
    events, conversions = list(db.tables["events"]), list(db.tables["conversions"])
    assert events and conversions
    live_ids = {f"rec-{i}" for i in range(30, 40)}
    assert not ({e["recipient_id"] for e in events} & live_ids)
    assert set(events[0]) == {"recipient_id", "type", "source", "occurred_at"}
    assert set(conversions[0]) == {"recipient_id", "mrr_cents", "source", "occurred_at"}

    simulate_responses(campaign_id)
    assert db.tables["events"] == events
    assert db.tables["conversions"] == conversions
