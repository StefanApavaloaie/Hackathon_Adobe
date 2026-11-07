# Owned by feature/delivery. Signed webhooks from Stripe (and later, optionally, Resend).
import logging
from typing import Protocol
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.errors import ServiceNotConfigured, not_implemented
from app.delivery.db import SupabaseStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PAID_STATUSES = ("paid", "no_payment_required")


class WebhookStore(Protocol):
    def is_processed(self, provider: str, event_id: str) -> bool: ...
    def mark_processed(self, provider: str, event_id: str) -> None: ...
    def get_recipient(self, recipient_id: str) -> dict | None: ...
    def add_conversion(self, row: dict) -> None: ...


class SupabaseWebhookStore(SupabaseStore):
    def is_processed(self, provider, event_id):
        rows = (
            self.db.table("processed_webhooks").select("event_id")
            .eq("provider", provider).eq("event_id", event_id).limit(1).execute().data
        )
        return bool(rows)

    def mark_processed(self, provider, event_id):
        self.db.table("processed_webhooks").upsert(
            {"provider": provider, "event_id": event_id}, on_conflict="provider,event_id", ignore_duplicates=True
        ).execute()

    def get_recipient(self, recipient_id):
        rows = self.db.table("recipients").select("id,source").eq("id", recipient_id).limit(1).execute().data
        return rows[0] if rows else None

    def add_conversion(self, row):
        # One conversion per recipient: a second purchase or a retried event adds nothing.
        self.db.table("conversions").upsert(row, on_conflict="recipient_id", ignore_duplicates=True).execute()


def get_webhook_store() -> WebhookStore:
    return SupabaseWebhookStore()


def _uuid_or_none(value) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        return None


def conversion_from_session(session: dict, recipient: dict | None) -> dict | None:
    """The conversion row for a completed Checkout Session, or None if it shouldn't count."""
    if session.get("payment_status") not in PAID_STATUSES:
        return None
    if recipient is None:
        return None
    if recipient.get("source") != "live":
        # Simulated recipients are never emailed. A real payment on one must not mix into live figures.
        return None
    return {
        "recipient_id": recipient["id"],
        "stripe_session_id": session["id"],
        # The discounted first payment, so recovered revenue reflects what was actually paid.
        "mrr_cents": session.get("amount_total") or 0,
        "source": "live",
    }


def handle_stripe_event(event: dict, store: WebhookStore) -> None:
    if event.get("type") != "checkout.session.completed":
        return
    session = event["data"]["object"]
    recipient_id = _uuid_or_none((session.get("metadata") or {}).get("recipient_id"))
    recipient = store.get_recipient(recipient_id) if recipient_id else None
    row = conversion_from_session(session, recipient)
    if row is None:
        logger.info("Ignored checkout %s: no live recipient or not paid", session.get("id"))
        return
    store.add_conversion(row)
    logger.info("Recorded conversion for recipient %s", row["recipient_id"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: WebhookStore = Depends(get_webhook_store),
) -> dict:
    if not settings.stripe_webhook_secret:
        raise ServiceNotConfigured("STRIPE_WEBHOOK_SECRET is not set")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, request.headers.get("stripe-signature"), settings.stripe_webhook_secret
        ).to_dict()
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature") from None

    event_id = event["id"]
    if store.is_processed("stripe", event_id):
        return {"received": True, "duplicate": True}
    # Mark processed only after handling succeeds; if handling fails, the 500
    # makes Stripe retry, and the conversion insert ignores duplicates.
    handle_stripe_event(event, store)
    store.mark_processed("stripe", event_id)
    return {"received": True}


@router.post("/resend")
async def resend_webhook():
    # Optional, and first on the design's cut list.
    not_implemented()
