# Owned by feature/delivery.
from app.stripe_import import import_customers, latest_per_customer, subscription_to_customer_row

CANCELED_AT = 1_762_000_000  # 2025-11-01T12:26:40Z
CANCELED_AT_ISO = "2025-11-01T12:26:40+00:00"


def subscription(
    sub_id="sub_1",
    customer_id="cus_1",
    email="user001@example.com",
    metadata=None,
    comment="Too expensive for a team our size.",
    feedback="too_expensive",
    canceled_at=CANCELED_AT,
    unit_amount=4900,
    quantity=1,
    interval="month",
    customer_metadata=None,
):
    return {
        "id": sub_id,
        "canceled_at": canceled_at,
        "metadata": metadata if metadata is not None else {"simulated": "true", "churned_at": "2026-09-01T10:00:00+00:00"},
        "cancellation_details": {"comment": comment, "feedback": feedback, "reason": "cancellation_requested"},
        "customer": {
            "id": customer_id,
            "object": "customer",
            "email": email,
            "name": "Alex Smith",
            "metadata": customer_metadata or {},
        },
        "items": {
            "data": [
                {
                    "quantity": quantity,
                    "price": {
                        "id": "price_1",
                        "product": "prod_1",
                        "unit_amount": unit_amount,
                        "lookup_key": "winback_pro_monthly",
                        "recurring": {"interval": interval, "interval_count": 1},
                    },
                }
            ]
        },
    }


def test_mapping_uses_churned_at_from_metadata():
    row = subscription_to_customer_row(subscription(), {"prod_1": "Pro plan"})
    assert row == {
        "stripe_customer_id": "cus_1",
        "email": "user001@example.com",
        "name": "Alex Smith",
        "plan": "Pro plan",
        "mrr_cents": 4900,
        "churned_at": "2026-09-01T10:00:00+00:00",
        "cancel_feedback": "too_expensive",
        "cancel_comment": "Too expensive for a team our size.",
        "is_simulated": True,
    }


def test_mapping_falls_back_to_canceled_at():
    row = subscription_to_customer_row(subscription(metadata={"simulated": "false"}))
    assert row["churned_at"] == CANCELED_AT_ISO


def test_mapping_reads_metadata_from_the_customer_when_the_subscription_has_none():
    row = subscription_to_customer_row(
        subscription(metadata={}, customer_metadata={"simulated": "false", "churned_at": "2026-10-01T00:00:00+00:00"})
    )
    assert row["is_simulated"] is False
    assert row["churned_at"] == "2026-10-01T00:00:00+00:00"


def test_mapping_reads_is_simulated():
    assert subscription_to_customer_row(subscription(metadata={"simulated": "false"}))["is_simulated"] is False
    assert subscription_to_customer_row(subscription(metadata={"simulated": "TRUE"}))["is_simulated"] is True


def test_mapping_treats_missing_simulated_flag_as_simulated_so_it_is_never_emailed():
    assert subscription_to_customer_row(subscription(metadata={}))["is_simulated"] is True


def test_mapping_handles_a_missing_comment():
    row = subscription_to_customer_row(subscription(comment=None, feedback=None))
    assert row["cancel_comment"] is None
    assert row["cancel_feedback"] is None
    sub = subscription()
    del sub["cancellation_details"]
    assert subscription_to_customer_row(sub)["cancel_comment"] is None


def test_mapping_blank_comment_becomes_none():
    assert subscription_to_customer_row(subscription(comment="   "))["cancel_comment"] is None


def test_mapping_plan_falls_back_to_lookup_key():
    assert subscription_to_customer_row(subscription())["plan"] == "winback_pro_monthly"


def test_mrr_multiplies_quantity_and_spreads_yearly_prices():
    assert subscription_to_customer_row(subscription(quantity=3))["mrr_cents"] == 14700
    assert subscription_to_customer_row(subscription(unit_amount=48000, interval="year"))["mrr_cents"] == 4000


def test_mapping_never_includes_unsubscribed_at():
    assert "unsubscribed_at" not in subscription_to_customer_row(subscription())


def test_mapping_skips_deleted_customers_and_customers_without_email():
    deleted = subscription()
    deleted["customer"] = {"id": "cus_1", "object": "customer", "deleted": True}
    assert subscription_to_customer_row(deleted) is None
    assert subscription_to_customer_row(subscription(email=None)) is None


def test_latest_per_customer_keeps_the_most_recent_cancellation():
    old = subscription(sub_id="sub_old", canceled_at=100)
    new = subscription(sub_id="sub_new", canceled_at=200)
    other = subscription(sub_id="sub_other", customer_id="cus_2")
    kept = latest_per_customer([new, other, old])
    assert sorted(sub["id"] for sub in kept) == ["sub_new", "sub_other"]


# --- import_customers with fake Stripe and Supabase -------------------------


class FakeList:
    def __init__(self, items):
        self.items = items

    def auto_paging_iter(self):
        return iter(self.items)


class FakeStripeObject(dict):
    def to_dict(self):
        return dict(self)


class FakeStripe:
    def __init__(self, subscriptions):
        stripe = self

        class Subscriptions:
            def list(self, params):
                stripe.list_params = params
                return FakeList([FakeStripeObject(sub) for sub in subscriptions])

        class Products:
            def retrieve(self, product_id):
                stripe.product_lookups.append(product_id)
                return FakeStripeObject(id=product_id, name="Pro plan")

        self.list_params = None
        self.product_lookups = []
        self.v1 = type("V1", (), {"subscriptions": Subscriptions(), "products": Products()})()


class FakeDb:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        db = self

        class Query:
            def upsert(self, rows, on_conflict):
                db.upserts.append((name, rows, on_conflict))
                return self

            def execute(self):
                return None

        return Query()


def test_import_upserts_cancelled_customers_by_stripe_id():
    stripe = FakeStripe([
        subscription(customer_id="cus_1", canceled_at=100),
        subscription(sub_id="sub_2", customer_id="cus_1", canceled_at=200, comment="Newer reason."),
        subscription(sub_id="sub_3", customer_id="cus_2", email="user002@example.com"),
    ])
    db = FakeDb()

    assert import_customers(stripe=stripe, db=db) == 2

    assert stripe.list_params["status"] == "canceled"
    assert "data.customer" in stripe.list_params["expand"]
    assert stripe.product_lookups == ["prod_1"]
    [(table, rows, on_conflict)] = db.upserts
    assert (table, on_conflict) == ("customers", "stripe_customer_id")
    assert {row["stripe_customer_id"]: row["cancel_comment"] for row in rows} == {
        "cus_1": "Newer reason.",
        "cus_2": "Too expensive for a team our size.",
    }
    assert all(row["plan"] == "Pro plan" for row in rows)


def test_import_with_no_cancellations_writes_nothing():
    db = FakeDb()
    assert import_customers(stripe=FakeStripe([]), db=db) == 0
    assert db.upserts == []
