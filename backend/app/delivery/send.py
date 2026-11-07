# Owned by feature/delivery. Approve a campaign, create its recipients, and send.
import logging
import secrets
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.delivery.email_templates import build_email
from app.services.email_client import is_allowed, send_email
from app.delivery.db import SupabaseStore
from app.simulator import simulate_responses

logger = logging.getLogger(__name__)

# Used only if the run's limits have no send_cap. Covers ~200 simulated plus a few live.
DEFAULT_SEND_CAP = 250
ALREADY_APPROVED = ("approved", "sending", "sent")


def new_token() -> str:
    """128 random bits, URL-safe."""
    return secrets.token_urlsafe(16)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


# --- pure planning ----------------------------------------------------------


def plan_recipients(
    *,
    members: list[dict],
    customers: dict[str, dict],
    variants: list[dict],
    send_cap: int,
    token_factory: Callable[[], str] = new_token,
) -> list[dict]:
    """Chooses who receives the campaign and which variant each gets.

    - Skips unsubscribed customers, customers already chosen for another cohort,
      and cohorts with no variants.
    - Live customers are chosen first, so the cap never drops the team inboxes.
      Simulated customers then fill the rest, taking one per cohort in turn.
    - Within each cohort, chosen customers sorted by ID alternate between variants.
    """
    variants_by_cohort: dict[str, list[dict]] = defaultdict(list)
    for v in sorted(variants, key=lambda v: v["label"]):
        variants_by_cohort[v["cohort_id"]].append(v)

    members_by_cohort: dict[str, list[str]] = defaultdict(list)
    for member in members:
        members_by_cohort[member["cohort_id"]].append(member["customer_id"])

    seen: set[str] = set()
    eligible: dict[str, list[str]] = {}
    for cohort_id in sorted(members_by_cohort):
        if not variants_by_cohort.get(cohort_id):
            continue
        ids = []
        for customer_id in sorted(set(members_by_cohort[cohort_id])):
            customer = customers.get(customer_id)
            if customer is None or customer.get("unsubscribed_at") or customer_id in seen:
                continue
            seen.add(customer_id)
            ids.append(customer_id)
        eligible[cohort_id] = ids

    def is_live(customer_id: str) -> bool:
        return customers[customer_id].get("is_simulated") is False

    chosen: list[tuple[str, str]] = [
        (cohort_id, cid) for cohort_id, ids in eligible.items() for cid in ids if is_live(cid)
    ][: max(send_cap, 0)]
    simulated = {cohort_id: [cid for cid in ids if not is_live(cid)] for cohort_id, ids in eligible.items()}
    position = 0
    while len(chosen) < send_cap and any(position < len(ids) for ids in simulated.values()):
        for cohort_id, ids in simulated.items():
            if position < len(ids) and len(chosen) < send_cap:
                chosen.append((cohort_id, ids[position]))
        position += 1

    chosen_by_cohort: dict[str, list[str]] = defaultdict(list)
    for cohort_id, customer_id in chosen:
        chosen_by_cohort[cohort_id].append(customer_id)

    rows = []
    for cohort_id in sorted(chosen_by_cohort):
        cohort_variants = variants_by_cohort[cohort_id]
        for index, customer_id in enumerate(sorted(chosen_by_cohort[cohort_id])):
            rows.append({
                "customer_id": customer_id,
                "variant_id": cohort_variants[index % len(cohort_variants)]["id"],
                "token": token_factory(),
                "source": "live" if is_live(customer_id) else "simulated",
            })
    return rows


# --- database access --------------------------------------------------------


class DeliveryStore(Protocol):
    def get_campaign(self, campaign_id: str) -> dict | None: ...
    def approve_draft(self, campaign_id: str, approved_by: str | None, approved_at: str) -> bool: ...
    def set_status(self, campaign_id: str, status: str) -> None: ...
    def get_run_limits(self, run_id: str) -> dict: ...
    def get_cohort_members(self, run_id: str) -> list[dict]: ...
    def get_customers(self, customer_ids: list[str]) -> list[dict]: ...
    def get_variants(self, campaign_id: str) -> list[dict]: ...
    def insert_recipients(self, campaign_id: str, rows: list[dict]) -> None: ...
    def get_recipients(self, campaign_id: str) -> list[dict]: ...
    def mark_sent(self, recipient_ids: list[str], sent_at: str, resend_message_id: str | None = None) -> None: ...
    def add_event(self, recipient_id: str, event_type: str, source: str) -> None: ...


def _chunks(items: list, size: int = 100):
    for start in range(0, len(items), size):
        yield items[start : start + size]


class SupabaseDeliveryStore(SupabaseStore):
    def get_campaign(self, campaign_id):
        rows = self.db.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute().data
        return rows[0] if rows else None

    def approve_draft(self, campaign_id, approved_by, approved_at):
        # Only a draft changes, so two approvals at once can't both start sending.
        rows = (
            self.db.table("campaigns")
            .update({"status": "approved", "approved_by": approved_by, "approved_at": approved_at})
            .eq("id", campaign_id)
            .eq("status", "draft")
            .execute()
            .data
        )
        return bool(rows)

    def set_status(self, campaign_id, status):
        self.db.table("campaigns").update({"status": status}).eq("id", campaign_id).execute()

    def get_run_limits(self, run_id):
        rows = self.db.table("agent_runs").select("limits").eq("id", run_id).limit(1).execute().data
        return (rows[0]["limits"] if rows else None) or {}

    def get_cohort_members(self, run_id):
        cohort_ids = [c["id"] for c in self.db.table("cohorts").select("id").eq("run_id", run_id).execute().data]
        members = []
        for chunk in _chunks(cohort_ids):
            members += (
                self.db.table("cohort_members").select("cohort_id,customer_id").in_("cohort_id", chunk)
                .range(0, 9999).execute().data
            )
        return members

    def get_customers(self, customer_ids):
        customers = []
        for chunk in _chunks(sorted(set(customer_ids))):
            customers += (
                self.db.table("customers").select("id,email,name,is_simulated,unsubscribed_at")
                .in_("id", chunk).execute().data
            )
        return customers

    def get_variants(self, campaign_id):
        return self.db.table("variants").select("*").eq("campaign_id", campaign_id).execute().data

    def insert_recipients(self, campaign_id, rows):
        payload = [{**row, "campaign_id": campaign_id} for row in rows]
        for chunk in _chunks(payload, 200):
            self.db.table("recipients").upsert(
                chunk, on_conflict="campaign_id,customer_id", ignore_duplicates=True
            ).execute()

    def get_recipients(self, campaign_id):
        return (
            self.db.table("recipients").select("*").eq("campaign_id", campaign_id).range(0, 9999).execute().data
        )

    def mark_sent(self, recipient_ids, sent_at, resend_message_id=None):
        update = {"sent_at": sent_at}
        if resend_message_id:
            update["resend_message_id"] = resend_message_id
        for chunk in _chunks(recipient_ids):
            self.db.table("recipients").update(update).in_("id", chunk).execute()

    def add_event(self, recipient_id, event_type, source):
        self.db.table("events").insert({"recipient_id": recipient_id, "type": event_type, "source": source}).execute()


def get_delivery_store() -> DeliveryStore:
    return SupabaseDeliveryStore()


def get_email_sender() -> Callable[..., str]:
    return send_email


# --- approve and send -------------------------------------------------------


class CampaignNotFound(Exception):
    pass


class CampaignRejected(Exception):
    pass


def approve(store: DeliveryStore, campaign_id: str, user_id: str, now: datetime) -> tuple[str, bool]:
    """Returns (status, started). `started` is True only for the call that approved a draft."""
    campaign = store.get_campaign(campaign_id)
    if campaign is None:
        raise CampaignNotFound(campaign_id)
    if campaign["status"] == "rejected":
        raise CampaignRejected(campaign_id)
    if campaign["status"] in ALREADY_APPROVED:
        return campaign["status"], False
    # approved_by is a uuid column; the development login's "dev-user" isn't one.
    approved_by = user_id if _is_uuid(user_id) else None
    if store.approve_draft(campaign_id, approved_by, now.isoformat()):
        return "approved", True
    # Someone else changed it between our read and our update.
    current = store.get_campaign(campaign_id) or {}
    if current.get("status") == "rejected":
        raise CampaignRejected(campaign_id)
    return current.get("status", "unknown"), False


def send_campaign(
    campaign_id: str,
    *,
    store: DeliveryStore,
    sender: Callable[..., str],
    allowlist: list[str],
    public_api_url: str,
    simulate: Callable[[UUID], None] = simulate_responses,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Creates recipients, emails allow-listed live ones, and hands simulated ones to the simulator.

    Safe to run again: existing recipients are kept and anyone with sent_at is skipped.
    """
    campaign = store.get_campaign(campaign_id)
    if campaign is None or campaign["status"] not in ("approved", "sending"):
        logger.warning("Not sending campaign %s: status is %s", campaign_id, campaign and campaign["status"])
        return

    limits = store.get_run_limits(campaign["run_id"])
    members = store.get_cohort_members(campaign["run_id"])
    customers = {c["id"]: c for c in store.get_customers([m["customer_id"] for m in members])}
    variants = {v["id"]: v for v in store.get_variants(campaign_id)}
    rows = plan_recipients(
        members=members,
        customers=customers,
        variants=list(variants.values()),
        send_cap=int(limits.get("send_cap") or DEFAULT_SEND_CAP),
    )
    store.insert_recipients(campaign_id, rows)
    store.set_status(campaign_id, "sending")

    recipients = [r for r in store.get_recipients(campaign_id) if not r.get("sent_at")]
    simulated_ids = [r["id"] for r in recipients if r["source"] == "simulated"]
    if simulated_ids:
        store.mark_sent(simulated_ids, now().isoformat())

    sent = 0
    for recipient in (r for r in recipients if r["source"] == "live"):
        customer = customers.get(recipient["customer_id"])
        variant = variants.get(recipient["variant_id"])
        if customer is None or variant is None or customer.get("unsubscribed_at"):
            continue
        # Checked immediately before each send. send_email checks again.
        if not is_allowed(customer["email"], allowlist):
            logger.warning("Skipped live recipient %s: address not on RECIPIENT_ALLOWLIST", recipient["id"])
            continue
        email = build_email(
            name=customer.get("name"),
            subject=variant["subject"],
            body_text=variant["body_text"],
            click_url=f"{public_api_url}/r/{recipient['token']}",
            unsubscribe_url=f"{public_api_url}/u/{recipient['token']}",
        )
        try:
            message_id = sender(
                to=customer["email"],
                subject=email.subject,
                html=email.html,
                text=email.text,
                headers=email.headers,
                idempotency_key=f"winback-{recipient['id']}",
            )
        except Exception:
            logger.exception("Email to live recipient %s failed", recipient["id"])
            continue
        store.mark_sent([recipient["id"]], now().isoformat(), message_id)
        store.add_event(recipient["id"], "sent", "live")
        sent += 1

    try:
        simulate(UUID(campaign_id))
    except Exception:
        logger.exception("Simulator failed for campaign %s", campaign_id)

    store.set_status(campaign_id, "sent")
    logger.info("Campaign %s sent: %d live emails, %d simulated", campaign_id, sent, len(simulated_ids))
