# Owned by feature/delivery. Public routes for the personalised win-back page, identified only by token.
import logging
from typing import Protocol

import stripe as stripe_sdk
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.contracts import PageContent
from app.delivery.db import SupabaseStore
from app.delivery.email_templates import first_name
from app.delivery.tokens import looks_like_token
from app.errors import ServiceNotConfigured
from app.services.stripe_client import get_stripe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pages", tags=["pages"])

# Created by scripts/seed_stripe.py.
PRICE_LOOKUP_KEY = "winback_pro_monthly"

# Shown if a variant's page_content ever fails the contract, so the link still works.
DEFAULT_PAGE = PageContent(
    headline="We'd love to have you back",
    subheadline="Pick up right where you left off.",
    reasons=[
        {"title": "Everything is still here", "body": "Your account and settings are ready when you are."},
        {"title": "No commitment", "body": "Cancel any time with one click."},
    ],
    objection_response="If it's still not right for you, you can cancel any time.",
    cta_label="Restart my subscription",
)


class PageStore(Protocol):
    def get_page_data(self, token: str) -> dict | None: ...
    def add_event(self, recipient_id: str, event_type: str, source: str) -> None: ...


class SupabasePageStore(SupabaseStore):
    def get_page_data(self, token):
        rows = (
            self.db.table("recipients")
            .select(
                "id,campaign_id,variant_id,source,"
                "customers(name,stripe_customer_id),"
                "variants(page_content,offers(id,label,percent_off,duration_months,stripe_coupon_id))"
            )
            .eq("token", token)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return None
        row = rows[0]
        variant = row.get("variants") or {}
        return {
            "recipient": {k: row[k] for k in ("id", "campaign_id", "variant_id", "source")},
            "customer": row.get("customers") or {},
            "page_content": variant.get("page_content"),
            "offer": variant.get("offers") or {},
        }

    def add_event(self, recipient_id, event_type, source):
        self.db.table("events").insert({"recipient_id": recipient_id, "type": event_type, "source": source}).execute()


def get_page_store() -> PageStore:
    return SupabasePageStore()


def get_stripe_client():
    return get_stripe()


def _load(store: PageStore, token: str) -> dict:
    data = store.get_page_data(token) if looks_like_token(token) else None
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link is no longer valid")
    return data


# --- pure helpers -----------------------------------------------------------


def page_response(data: dict) -> dict:
    """What the public page may see: wording, the offer's terms, and a first name. Nothing else."""
    try:
        content = PageContent.model_validate(data.get("page_content"))
    except ValidationError:
        logger.warning("Variant %s has invalid page_content; using default copy", data["recipient"]["variant_id"])
        content = DEFAULT_PAGE
    offer = data["offer"]
    return {
        "page_content": content.model_dump(),
        "offer": {
            "label": offer.get("label"),
            "percent_off": offer.get("percent_off", 0),
            "duration_months": offer.get("duration_months", 0),
        },
        "first_name": first_name(data["customer"].get("name")),
    }


def checkout_params(data: dict, *, price_id: str, frontend_origin: str, token: str) -> dict:
    """Builds the Checkout Session from stored data only. Nothing from the browser is used."""
    recipient, offer = data["recipient"], data["offer"]
    customer_id = data["customer"].get("stripe_customer_id")
    if not customer_id:
        raise ServiceNotConfigured("Recipient has no Stripe customer")
    metadata = {
        "recipient_id": recipient["id"],
        "campaign_id": recipient["campaign_id"],
        "variant_id": recipient["variant_id"],
    }
    params = {
        "mode": "subscription",
        "customer": customer_id,
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{frontend_origin}/thanks",
        "cancel_url": f"{frontend_origin}/w/{token}",
        "client_reference_id": recipient["id"],
        "metadata": metadata,
        "subscription_data": {"metadata": metadata},
    }
    if (offer.get("percent_off") or 0) > 0:
        # Never fall back to full price: a missing coupon is a setup error, not a sale.
        if not offer.get("stripe_coupon_id"):
            raise ServiceNotConfigured("Offer has no Stripe coupon; run scripts.seed_stripe")
        params["discounts"] = [{"coupon": offer["stripe_coupon_id"]}]
    return params


_price_ids: dict[str, str] = {}


def _price_id(stripe) -> str:
    if PRICE_LOOKUP_KEY not in _price_ids:
        prices = stripe.v1.prices.list({"lookup_keys": [PRICE_LOOKUP_KEY], "active": True, "limit": 1})
        if not prices.data:
            raise ServiceNotConfigured(f"No Stripe price with lookup key {PRICE_LOOKUP_KEY}; run scripts.seed_stripe")
        _price_ids[PRICE_LOOKUP_KEY] = prices.data[0].id
    return _price_ids[PRICE_LOOKUP_KEY]


# --- routes -----------------------------------------------------------------


@router.get("/{token}")
def get_page(token: str, background: BackgroundTasks, store: PageStore = Depends(get_page_store)) -> dict:
    data = _load(store, token)
    recipient = data["recipient"]
    background.add_task(store.add_event, recipient["id"], "page_viewed", recipient["source"])
    return page_response(data)


# Takes no request body on purpose: the offer always comes from the token.
@router.post("/{token}/checkout")
def create_checkout(
    token: str,
    settings: Settings = Depends(get_settings),
    store: PageStore = Depends(get_page_store),
    stripe=Depends(get_stripe_client),
) -> dict:
    data = _load(store, token)
    params = checkout_params(data, price_id=_price_id(stripe), frontend_origin=settings.frontend_origin, token=token)
    try:
        session = stripe.v1.checkout.sessions.create(params)
    except stripe_sdk.StripeError as exc:
        logger.error("Stripe Checkout failed for recipient %s: %s", data["recipient"]["id"], exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Checkout is unavailable, please try again") from None
    recipient = data["recipient"]
    store.add_event(recipient["id"], "checkout_started", recipient["source"])
    return {"url": session.url}
