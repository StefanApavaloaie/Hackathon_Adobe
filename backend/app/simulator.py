"""Simulated responses for seeded customers (step 7).

The hidden rates below are never shown to the LLM. Delivery calls
`simulate_responses(campaign_id)` after sending.
"""
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.services.supabase_client import get_supabase

# ---------------------------------------------------------------------------
# 1. Hidden rates
# ---------------------------------------------------------------------------
# (click_rate, conversion_after_click_rate) per [cancel_feedback][offer_band]
OFFER_BANDS = ("0%", "1-15%", "16-30%", "31-50%")

HIDDEN_RATES: dict[str, dict[str, tuple[float, float]]] = {
    "too_expensive": {
        "0%": (0.05, 0.10),
        "1-15%": (0.15, 0.20),
        "16-30%": (0.35, 0.40),
        "31-50%": (0.60, 0.50),
    },
    "missing_features": {
        "0%": (0.50, 0.40),
        "1-15%": (0.30, 0.30),
        "16-30%": (0.20, 0.25),
        "31-50%": (0.10, 0.20),
    },
    "switched_service": {
        "0%": (0.10, 0.10),
        "1-15%": (0.20, 0.25),
        "16-30%": (0.40, 0.45),
        "31-50%": (0.50, 0.55),
    },
    "unused": {
        "0%": (0.20, 0.15),
        "1-15%": (0.25, 0.20),
        "16-30%": (0.30, 0.25),
        "31-50%": (0.30, 0.30),
    },
    "too_complex": {
        "0%": (0.35, 0.30),
        "1-15%": (0.25, 0.25),
        "16-30%": (0.20, 0.20),
        "31-50%": (0.20, 0.20),
    },
    "low_quality": {
        "0%": (0.30, 0.25),
        "1-15%": (0.20, 0.20),
        "16-30%": (0.15, 0.15),
        "31-50%": (0.15, 0.15),
    },
    "customer_service": {
        "0%": (0.25, 0.20),
        "1-15%": (0.25, 0.25),
        "16-30%": (0.25, 0.25),
        "31-50%": (0.25, 0.25),
    },
    # Generic fallback for any other or missing reason
    "default": {
        "0%": (0.10, 0.10),
        "1-15%": (0.20, 0.20),
        "16-30%": (0.30, 0.30),
        "31-50%": (0.40, 0.40),
    },
}

WINDOW_SECONDS = 60
SIMULATED_EVENT_TYPES = ("clicked", "page_viewed", "checkout_started")


def _get_offer_band(percent_off: int) -> str:
    if percent_off <= 0:
        return "0%"
    if percent_off <= 15:
        return "1-15%"
    if percent_off <= 30:
        return "16-30%"
    return "31-50%"


# ---------------------------------------------------------------------------
# 2. Pure function (maths and planning)
# ---------------------------------------------------------------------------
def plan_outcomes(
    recipients: list[dict],
    offers: dict[str, dict],
    rng: random.Random,
    now: datetime | None = None,
    rates: dict[str, dict[str, tuple[float, float]]] = HIDDEN_RATES,
) -> tuple[list[dict], list[dict]]:
    """Plan events and conversions deterministically from `rng`.

    Each recipient is a dict with `recipient_id`, `source`, `cancel_feedback`,
    `mrr_cents` and `offer_id`. Only `source == 'simulated'` recipients are used.
    Every timestamp falls within WINDOW_SECONDS of `now`.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    events: list[dict] = []
    conversions: list[dict] = []

    for rec in recipients:
        if rec.get("source") != "simulated":
            continue

        feedback = rec.get("cancel_feedback")
        if feedback not in rates:
            feedback = "default"

        offer = offers.get(rec.get("offer_id"), {"percent_off": 0})
        percent_off = offer.get("percent_off") or 0
        click_rate, conv_rate = rates[feedback][_get_offer_band(percent_off)]

        # Draw both decisions and all offsets up front, so each recipient
        # consumes the same number of random values whatever the outcome.
        clicked = rng.random() < click_rate
        converted = rng.random() < conv_rate
        t_click = rng.uniform(0, WINDOW_SECONDS - 15)
        t_view = t_click + rng.uniform(1, 5)
        t_checkout = t_view + rng.uniform(1, 5)
        t_paid = t_checkout + rng.uniform(1, 5)

        if not clicked:
            continue

        rid = rec["recipient_id"]

        def at(offset: float) -> str:
            return (now + timedelta(seconds=offset)).isoformat()

        events.append({"recipient_id": rid, "type": "clicked", "source": "simulated", "occurred_at": at(t_click)})
        events.append({"recipient_id": rid, "type": "page_viewed", "source": "simulated", "occurred_at": at(t_view)})

        if converted:
            events.append(
                {"recipient_id": rid, "type": "checkout_started", "source": "simulated", "occurred_at": at(t_checkout)}
            )
            mrr_cents = rec.get("mrr_cents") or 0
            conversions.append(
                {
                    "recipient_id": rid,
                    "mrr_cents": int(mrr_cents * (100 - percent_off) / 100),
                    "source": "simulated",
                    "occurred_at": at(t_paid),
                }
            )

    return events, conversions


# ---------------------------------------------------------------------------
# 3. Database wrapper
# ---------------------------------------------------------------------------
def simulate_responses(campaign_id: UUID) -> None:
    db = get_supabase()
    cid = str(campaign_id)

    recipients = (
        db.table("recipients")
        .select("id, customer_id, variant_id, source")
        .eq("campaign_id", cid)
        .eq("source", "simulated")
        .execute()
        .data
    )
    if not recipients:
        return

    recipient_ids = [r["id"] for r in recipients]

    # Idempotency: skip recipients that already have simulated responses.
    already = {
        e["recipient_id"]
        for e in db.table("events")
        .select("recipient_id")
        .in_("recipient_id", recipient_ids)
        .in_("type", list(SIMULATED_EVENT_TYPES))
        .execute()
        .data
    }
    already |= {
        c["recipient_id"]
        for c in db.table("conversions").select("recipient_id").in_("recipient_id", recipient_ids).execute().data
    }

    customer_ids = list({r["customer_id"] for r in recipients})
    variant_ids = list({r["variant_id"] for r in recipients})

    customers = {
        c["id"]: c
        for c in db.table("customers").select("id, cancel_feedback, mrr_cents").in_("id", customer_ids).execute().data
    }
    variants = {v["id"]: v for v in db.table("variants").select("id, offer_id").in_("id", variant_ids).execute().data}
    offers = {o["id"]: o for o in db.table("offers").select("id, percent_off, duration_months").execute().data}

    enriched = []
    # Sort for a stable order, so the seeded RNG gives repeatable results.
    for r in sorted(recipients, key=lambda r: r["id"]):
        customer = customers.get(r["customer_id"], {})
        variant = variants.get(r["variant_id"], {})
        enriched.append(
            {
                "recipient_id": r["id"],
                "source": r["source"],
                "cancel_feedback": customer.get("cancel_feedback"),
                "mrr_cents": customer.get("mrr_cents") or 0,
                "offer_id": variant.get("offer_id"),
            }
        )

    # Plan for every recipient so the RNG sequence doesn't depend on what was
    # already written, then keep only the new ones.
    events, conversions = plan_outcomes(enriched, offers, random.Random(cid))
    events = [e for e in events if e["recipient_id"] not in already]
    conversions = [c for c in conversions if c["recipient_id"] not in already]

    if events:
        db.table("events").insert(events).execute()
    if conversions:
        db.table("conversions").insert(conversions).execute()
