# Owned by feature/delivery. Keep the name and signature: feature/agent calls it when starting a run.
import logging
from datetime import UTC, datetime
from typing import Any

from app.services.stripe_client import get_stripe
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

UPSERT_BATCH_SIZE = 200


def _metadata(subscription: dict) -> dict:
    """Seeded metadata lives on the subscription, with the customer as a fallback."""
    customer = subscription.get("customer")
    customer_metadata = customer.get("metadata") if isinstance(customer, dict) else None
    return {**(customer_metadata or {}), **(subscription.get("metadata") or {})}


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _monthly_cents(subscription: dict) -> int:
    total = 0.0
    for item in (subscription.get("items") or {}).get("data") or []:
        price = item.get("price") or {}
        amount = price.get("unit_amount") or 0
        quantity = item.get("quantity") or 1
        recurring = price.get("recurring") or {}
        months = {"day": 1 / 30, "week": 7 / 30, "month": 1, "year": 12}.get(recurring.get("interval"), 1)
        months *= recurring.get("interval_count") or 1
        total += amount * quantity / months
    return round(total)


def _plan_name(subscription: dict, plan_names: dict[str, str]) -> str | None:
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    product = price.get("product")
    product_id = product.get("id") if isinstance(product, dict) else product
    if isinstance(product, dict) and product.get("name"):
        return product["name"]
    return plan_names.get(product_id) or price.get("nickname") or price.get("lookup_key") or product_id


def subscription_to_customer_row(subscription: dict, plan_names: dict[str, str] | None = None) -> dict | None:
    """Maps one cancelled Stripe subscription (with `customer` expanded) to a `customers` row.

    Returns None when the customer is deleted or has no email. Never includes
    `unsubscribed_at`, so an upsert can't overwrite an unsubscribe.
    """
    customer = subscription.get("customer")
    if not isinstance(customer, dict) or customer.get("deleted") or not customer.get("email"):
        return None

    metadata = _metadata(subscription)
    details = subscription.get("cancellation_details") or {}
    churned_at = metadata.get("churned_at")
    if not churned_at and subscription.get("canceled_at"):
        churned_at = datetime.fromtimestamp(subscription["canceled_at"], UTC).isoformat()

    return {
        "stripe_customer_id": customer["id"],
        "email": customer["email"],
        "name": customer.get("name"),
        "plan": _plan_name(subscription, plan_names or {}),
        "mrr_cents": _monthly_cents(subscription),
        "churned_at": churned_at,
        "cancel_feedback": _blank_to_none(details.get("feedback")),
        "cancel_comment": _blank_to_none(details.get("comment")),
        # Anything not explicitly marked live is treated as simulated, so it is never emailed.
        "is_simulated": str(metadata.get("simulated", "true")).strip().lower() != "false",
    }


def _customer_id(subscription: dict) -> str | None:
    customer = subscription.get("customer")
    return customer.get("id") if isinstance(customer, dict) else customer


def latest_per_customer(subscriptions: list[dict]) -> list[dict]:
    """Keeps each customer's most recent cancellation. One upsert can't touch a row twice."""
    latest: dict[str, dict] = {}
    for subscription in subscriptions:
        customer_id = _customer_id(subscription)
        if customer_id is None:
            continue
        kept = latest.get(customer_id)
        if kept is None or (subscription.get("canceled_at") or 0) > (kept.get("canceled_at") or 0):
            latest[customer_id] = subscription
    return list(latest.values())


def _product_ids(subscriptions: list[dict]) -> set[str]:
    ids = set()
    for subscription in subscriptions:
        for item in (subscription.get("items") or {}).get("data") or []:
            product = (item.get("price") or {}).get("product")
            if isinstance(product, str):
                ids.add(product)
    return ids


def import_customers(*, stripe=None, db=None) -> int:
    """Imports every cancelled Stripe subscriber into `customers` and returns how many.

    `stripe` and `db` are for tests; callers use the defaults.
    """
    stripe = stripe or get_stripe()
    db = db or get_supabase()

    listing = stripe.v1.subscriptions.list({"status": "canceled", "limit": 100, "expand": ["data.customer"]})
    subscriptions = latest_per_customer([sub.to_dict() for sub in listing.auto_paging_iter()])

    # Stripe can't expand products this deep in a list, so look each one up once.
    plan_names = {}
    for product_id in sorted(_product_ids(subscriptions)):
        plan_names[product_id] = stripe.v1.products.retrieve(product_id).to_dict().get("name") or product_id

    rows = [row for sub in subscriptions if (row := subscription_to_customer_row(sub, plan_names))]
    for start in range(0, len(rows), UPSERT_BATCH_SIZE):
        db.table("customers").upsert(rows[start : start + UPSERT_BATCH_SIZE], on_conflict="stripe_customer_id").execute()

    skipped = len(subscriptions) - len(rows)
    if skipped:
        logger.info("Skipped %d cancelled subscriptions with a deleted customer or no email", skipped)
    return len(rows)
