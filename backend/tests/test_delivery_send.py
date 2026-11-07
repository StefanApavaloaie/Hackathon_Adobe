# Owned by feature/delivery.
import uuid
from collections import Counter
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.delivery.send import approve, get_delivery_store, get_email_sender, plan_recipients, send_campaign

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
CAMPAIGN = "11111111-1111-1111-1111-111111111111"
RUN = "22222222-2222-2222-2222-222222222222"
COHORT_1 = "c1"
COHORT_2 = "c2"
ALLOWED = "ana@team.dev"


def customer(cid, simulated=True, email=None, unsubscribed=False):
    return {
        "id": cid,
        "email": email or f"{cid}@example.com",
        "name": f"Name {cid}",
        "is_simulated": simulated,
        "unsubscribed_at": "2026-11-01T00:00:00+00:00" if unsubscribed else None,
    }


def variant(vid, cohort, label):
    return {"id": vid, "cohort_id": cohort, "label": label, "subject": f"Subject {vid}", "body_text": f"Body {vid}"}


VARIANTS = [variant("v1a", COHORT_1, "A"), variant("v1b", COHORT_1, "B"), variant("v2a", COHORT_2, "A"), variant("v2b", COHORT_2, "B")]


def tokens():
    counter = iter(range(10_000))
    return lambda: f"tok{next(counter)}"


def plan(members, customers, send_cap=100, variants=VARIANTS):
    return plan_recipients(
        members=members,
        customers={c["id"]: c for c in customers},
        variants=variants,
        send_cap=send_cap,
        token_factory=tokens(),
    )


# --- plan_recipients --------------------------------------------------------


def test_variants_alternate_within_a_cohort_sorted_by_customer_id():
    customers = [customer(f"u{i}") for i in range(4)]
    members = [{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in reversed(customers)]
    rows = plan(members, customers)
    assert [(row["customer_id"], row["variant_id"]) for row in rows] == [
        ("u0", "v1a"), ("u1", "v1b"), ("u2", "v1a"), ("u3", "v1b"),
    ]


def test_send_cap_is_respected_and_shared_across_cohorts():
    customers = [customer(f"u{i:02d}") for i in range(20)]
    members = [{"cohort_id": COHORT_1 if i < 10 else COHORT_2, "customer_id": c["id"]} for i, c in enumerate(customers)]
    rows = plan(members, customers, send_cap=6)
    assert len(rows) == 6
    assert Counter(row["variant_id"][:2] for row in rows) == {"v1": 3, "v2": 3}


def test_live_customers_are_kept_when_the_cap_cuts_the_list():
    customers = [customer(f"u{i:02d}") for i in range(10)] + [customer("zz-live", simulated=False, email=ALLOWED)]
    members = [{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in customers]
    rows = plan(members, customers, send_cap=3)
    assert "zz-live" in {row["customer_id"] for row in rows}
    assert len(rows) == 3


def test_unsubscribed_customers_are_excluded():
    customers = [customer("u1"), customer("u2", unsubscribed=True)]
    members = [{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in customers]
    assert [row["customer_id"] for row in plan(members, customers)] == ["u1"]


def test_source_follows_is_simulated():
    customers = [customer("u1"), customer("u2", simulated=False)]
    members = [{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in customers]
    assert {row["customer_id"]: row["source"] for row in plan(members, customers)} == {"u1": "simulated", "u2": "live"}


def test_a_customer_in_two_cohorts_gets_one_recipient():
    customers = [customer("u1")]
    members = [{"cohort_id": COHORT_1, "customer_id": "u1"}, {"cohort_id": COHORT_2, "customer_id": "u1"}]
    assert len(plan(members, customers)) == 1


def test_cohorts_without_variants_are_skipped():
    customers = [customer("u1"), customer("u2")]
    members = [{"cohort_id": COHORT_1, "customer_id": "u1"}, {"cohort_id": "no-variants", "customer_id": "u2"}]
    assert [row["customer_id"] for row in plan(members, customers)] == ["u1"]


def test_default_tokens_have_128_bits():
    rows = plan_recipients(
        members=[{"cohort_id": COHORT_1, "customer_id": "u1"}],
        customers={"u1": customer("u1")},
        variants=VARIANTS,
        send_cap=10,
    )
    # token_urlsafe(16) encodes 16 random bytes as 22 characters.
    assert len(rows[0]["token"]) == 22


# --- fakes ------------------------------------------------------------------


class FakeStore:
    def __init__(self, status="draft", customers=None, members=None, send_cap=100):
        self.campaign = {"id": CAMPAIGN, "run_id": RUN, "status": status, "approved_by": None, "approved_at": None}
        self.limits = {"send_cap": send_cap, "max_percent_off": 50}
        self.customers = {c["id"]: c for c in (customers or [])}
        self.members = members or []
        self.variants = list(VARIANTS)
        self.recipients: list[dict] = []
        self.events: list[tuple] = []
        self.statuses: list[str] = []

    def get_campaign(self, campaign_id):
        return dict(self.campaign) if campaign_id == CAMPAIGN else None

    def approve_draft(self, campaign_id, approved_by, approved_at):
        if self.campaign["status"] != "draft":
            return False
        self.campaign.update(status="approved", approved_by=approved_by, approved_at=approved_at)
        self.statuses.append("approved")
        return True

    def set_status(self, campaign_id, status):
        self.campaign["status"] = status
        self.statuses.append(status)

    def get_run_limits(self, run_id):
        return self.limits

    def get_cohort_members(self, run_id):
        return self.members

    def get_customers(self, customer_ids):
        return [self.customers[cid] for cid in customer_ids if cid in self.customers]

    def get_variants(self, campaign_id):
        return self.variants

    def insert_recipients(self, campaign_id, rows):
        existing = {r["customer_id"] for r in self.recipients}
        for row in rows:
            if row["customer_id"] not in existing:
                self.recipients.append({**row, "id": f"r-{row['customer_id']}", "campaign_id": campaign_id,
                                        "sent_at": None, "resend_message_id": None})

    def get_recipients(self, campaign_id):
        return [dict(r) for r in self.recipients]

    def mark_sent(self, recipient_ids, sent_at, resend_message_id=None):
        for r in self.recipients:
            if r["id"] in recipient_ids:
                r["sent_at"] = sent_at
                r["resend_message_id"] = resend_message_id

    def add_event(self, recipient_id, event_type, source):
        self.events.append((recipient_id, event_type, source))


class FakeSender:
    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def __call__(self, *, to, subject, html, text, headers, idempotency_key):
        if to in self.fail_for:
            raise RuntimeError("Resend is down")
        self.sent.append({"to": to, "subject": subject, "html": html, "idempotency_key": idempotency_key})
        return f"msg-{to}"


def mixed_store(**overrides):
    customers = [
        customer("live-ok", simulated=False, email=ALLOWED),
        customer("live-blocked", simulated=False, email="stranger@gmail.com"),
        customer("sim-1"),
        customer("sim-2"),
    ]
    members = [{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in customers]
    return FakeStore(status="approved", customers=customers, members=members, **overrides)


def run_send(store, sender, simulated_calls=None, allowlist=(ALLOWED,)):
    calls = simulated_calls if simulated_calls is not None else []
    send_campaign(
        CAMPAIGN, store=store, sender=sender, allowlist=list(allowlist),
        public_api_url="https://api.test", simulate=calls.append, now=lambda: NOW,
    )
    return calls


# --- send_campaign ----------------------------------------------------------


def test_only_allowlisted_live_recipients_get_email():
    store, sender = mixed_store(), FakeSender()
    run_send(store, sender)
    assert [email["to"] for email in sender.sent] == [ALLOWED]
    blocked = next(r for r in store.recipients if r["customer_id"] == "live-blocked")
    assert blocked["sent_at"] is None


def test_simulated_recipients_are_marked_sent_but_never_emailed():
    store, sender = mixed_store(), FakeSender()
    run_send(store, sender)
    simulated = [r for r in store.recipients if r["source"] == "simulated"]
    assert len(simulated) == 2
    assert all(r["sent_at"] == NOW.isoformat() for r in simulated)
    assert not any(email["to"].endswith("@example.com") for email in sender.sent)


def test_live_send_saves_message_id_and_records_sent_event():
    store, sender = mixed_store(), FakeSender()
    run_send(store, sender)
    live = next(r for r in store.recipients if r["customer_id"] == "live-ok")
    assert live["resend_message_id"] == f"msg-{ALLOWED}"
    assert store.events == [(live["id"], "sent", "live")]
    assert sender.sent[0]["idempotency_key"] == f"winback-{live['id']}"
    assert f"https://api.test/r/{live['token']}" in sender.sent[0]["html"]


def test_send_moves_to_sending_then_sent_and_calls_the_simulator():
    store = mixed_store()
    calls = run_send(store, FakeSender())
    assert store.statuses == ["sending", "sent"]
    assert calls == [uuid.UUID(CAMPAIGN)]


def test_one_failed_email_does_not_stop_the_campaign():
    customers = [customer("live-a", simulated=False, email="a@team.dev"), customer("live-b", simulated=False, email="b@team.dev")]
    store = FakeStore(status="approved", customers=customers,
                      members=[{"cohort_id": COHORT_1, "customer_id": c["id"]} for c in customers])
    sender = FakeSender(fail_for={"a@team.dev"})
    run_send(store, sender, allowlist=("a@team.dev", "b@team.dev"))
    assert [email["to"] for email in sender.sent] == ["b@team.dev"]
    assert store.campaign["status"] == "sent"


def test_a_simulator_error_still_finishes_the_campaign():
    store = mixed_store()

    def broken(campaign_id):
        raise RuntimeError("simulator bug")

    send_campaign(CAMPAIGN, store=store, sender=FakeSender(), allowlist=[ALLOWED],
                  public_api_url="https://api.test", simulate=broken, now=lambda: NOW)
    assert store.campaign["status"] == "sent"


def test_sending_again_sends_nothing_new():
    store, sender = mixed_store(), FakeSender()
    run_send(store, sender)
    store.campaign["status"] = "approved"
    run_send(store, sender)
    assert len(sender.sent) == 1
    assert len(store.recipients) == 4


def test_send_respects_the_runs_send_cap():
    store = mixed_store(send_cap=2)
    run_send(store, FakeSender())
    assert len(store.recipients) == 2


def test_send_does_nothing_for_a_draft_campaign():
    store = mixed_store()
    store.campaign["status"] = "draft"
    sender = FakeSender()
    run_send(store, sender)
    assert store.recipients == [] and sender.sent == []


# --- approve ----------------------------------------------------------------


def test_approve_records_who_and_when():
    store = FakeStore()
    user_id = str(uuid.uuid4())
    assert approve(store, CAMPAIGN, user_id, NOW) == ("approved", True)
    assert store.campaign["approved_by"] == user_id
    assert store.campaign["approved_at"] == NOW.isoformat()


def test_approve_with_a_non_uuid_dev_user_leaves_approved_by_empty():
    store = FakeStore()
    approve(store, CAMPAIGN, "dev-user", NOW)
    assert store.campaign["approved_by"] is None


@pytest.fixture
def api(client):
    app = client.app
    store, sender = FakeStore(customers=[customer("live-ok", simulated=False, email=ALLOWED)],
                              members=[{"cohort_id": COHORT_1, "customer_id": "live-ok"}]), FakeSender()
    settings = app.dependency_overrides[get_settings]().model_copy(update={"recipient_allowlist": ALLOWED})
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_delivery_store] = lambda: store
    app.dependency_overrides[get_email_sender] = lambda: sender
    return TestClient(app), store, sender


def test_approve_route_returns_202_and_sends_in_the_background(api):
    http, store, sender = api
    response = http.post(f"/api/campaigns/{CAMPAIGN}/approve")
    assert response.status_code == 202
    assert response.json() == {"campaign_id": CAMPAIGN, "status": "approved"}
    assert store.campaign["status"] == "sent"
    assert [email["to"] for email in sender.sent] == [ALLOWED]


def test_approving_twice_has_no_further_effect(api):
    http, store, sender = api
    http.post(f"/api/campaigns/{CAMPAIGN}/approve")
    response = http.post(f"/api/campaigns/{CAMPAIGN}/approve")
    assert response.status_code == 200
    assert response.json() == {"campaign_id": CAMPAIGN, "status": "sent"}
    assert len(sender.sent) == 1
    assert store.statuses == ["approved", "sending", "sent"]


def test_approving_a_rejected_campaign_returns_409(api):
    http, store, sender = api
    store.campaign["status"] = "rejected"
    assert http.post(f"/api/campaigns/{CAMPAIGN}/approve").status_code == 409
    assert sender.sent == []


def test_approving_an_unknown_campaign_returns_404(api):
    http, _, _ = api
    assert http.post(f"/api/campaigns/{uuid.uuid4()}/approve").status_code == 404
