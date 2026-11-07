# Owned by feature/delivery. Keep the model fields and the compute_metrics signature:
# feature/agent's report reads them. Change the models only through a pull request to main.
from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.delivery.db import SupabaseStore


class Counts(BaseModel):
    recipients: int = 0
    clicks: int = 0
    page_views: int = 0
    checkouts_started: int = 0
    conversions: int = 0
    mrr_recovered_cents: int = 0


class VariantMetrics(Counts):
    cohort_id: UUID
    variant_id: UUID
    variant_label: str


class SourceMetrics(Counts):
    """Totals for one source, plus the breakdown by variant."""

    variants: list[VariantMetrics] = []


class CampaignMetrics(BaseModel):
    """Live and simulated results are kept apart and must never be added together."""

    campaign_id: UUID
    live: SourceMetrics
    simulated: SourceMetrics


# Event type -> Counts field. Each counts distinct recipients, so a double click counts once.
FUNNEL = {"clicked": "clicks", "page_viewed": "page_views", "checkout_started": "checkouts_started"}
SOURCES = ("live", "simulated")


def _at(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def aggregate(
    campaign_id: UUID, recipients: list[dict], events: list[dict], conversions: list[dict], now: datetime
) -> CampaignMetrics:
    """Counts the funnel per source and per variant.

    `recipients` rows carry id, source, variant_id, cohort_id and variant_label.
    Anything dated after `now` is ignored: the simulator writes times up to a minute ahead.
    A row's source is its recipient's source, so live and simulated never mix.
    """
    by_id = {r["id"]: r for r in recipients}

    # (source, variant_id) -> field -> set of recipient IDs
    reached: dict[tuple[str, str], dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for e in events:
        r = by_id.get(e["recipient_id"])
        field = FUNNEL.get(e["type"])
        if r is None or field is None or _at(e["occurred_at"]) > now:
            continue
        reached[(r["source"], r["variant_id"])][field].add(r["id"])

    converted: dict[tuple[str, str], list[int]] = defaultdict(list)
    for c in conversions:
        r = by_id.get(c["recipient_id"])
        if r is None or _at(c["occurred_at"]) > now:
            continue
        converted[(r["source"], r["variant_id"])].append(int(c["mrr_cents"] or 0))

    variants: dict[tuple[str, str], VariantMetrics] = {}
    for r in sorted(recipients, key=lambda r: (str(r["cohort_id"]), r["variant_label"], str(r["variant_id"]))):
        key = (r["source"], r["variant_id"])
        if key not in variants:
            variants[key] = VariantMetrics(
                cohort_id=r["cohort_id"], variant_id=r["variant_id"], variant_label=r["variant_label"]
            )
        variants[key].recipients += 1
    for key, metrics in variants.items():
        for field, ids in reached.get(key, {}).items():
            setattr(metrics, field, len(ids))
        metrics.conversions = len(converted.get(key, []))
        metrics.mrr_recovered_cents = sum(converted.get(key, []))

    totals = {}
    for source in SOURCES:
        rows = [m for (s, _), m in variants.items() if s == source]
        totals[source] = SourceMetrics(
            recipients=sum(m.recipients for m in rows),
            clicks=sum(m.clicks for m in rows),
            page_views=sum(m.page_views for m in rows),
            checkouts_started=sum(m.checkouts_started for m in rows),
            conversions=sum(m.conversions for m in rows),
            mrr_recovered_cents=sum(m.mrr_recovered_cents for m in rows),
            variants=rows,
        )
    return CampaignMetrics(campaign_id=campaign_id, live=totals["live"], simulated=totals["simulated"])


# --- database access --------------------------------------------------------


class MetricsStore(Protocol):
    def get_recipients(self, campaign_id: str) -> list[dict]: ...
    def get_events(self, recipient_ids: list[str], until: datetime) -> list[dict]: ...
    def get_conversions(self, recipient_ids: list[str], until: datetime) -> list[dict]: ...


PAGE_SIZE = 1000  # Supabase returns at most 1000 rows per request.
ID_CHUNK = 100  # Keeps the `in (...)` filter's URL short.


def _all_rows(query_factory) -> list[dict]:
    rows, start = [], 0
    while True:
        page = query_factory().range(start, start + PAGE_SIZE - 1).execute().data
        rows += page
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


class SupabaseMetricsStore(SupabaseStore):
    def get_recipients(self, campaign_id):
        rows = _all_rows(
            lambda: self.db.table("recipients")
            .select("id,source,variant_id,variants(cohort_id,label)")
            .eq("campaign_id", campaign_id)
            .order("id")
        )
        return [
            {
                "id": r["id"],
                "source": r["source"],
                "variant_id": r["variant_id"],
                "cohort_id": (r.get("variants") or {}).get("cohort_id"),
                "variant_label": (r.get("variants") or {}).get("label", "?"),
            }
            for r in rows
        ]

    def _by_recipients(self, table, columns, recipient_ids, until):
        rows = []
        for start in range(0, len(recipient_ids), ID_CHUNK):
            chunk = recipient_ids[start : start + ID_CHUNK]
            rows += _all_rows(
                lambda: self.db.table(table)
                .select(columns)
                .in_("recipient_id", chunk)
                .lte("occurred_at", until.isoformat())
                .order("id")
            )
        return rows

    def get_events(self, recipient_ids, until):
        return self._by_recipients(
            "events", "recipient_id,type,occurred_at", recipient_ids, until
        )

    def get_conversions(self, recipient_ids, until):
        return self._by_recipients("conversions", "recipient_id,mrr_cents,occurred_at", recipient_ids, until)


def get_metrics_store() -> MetricsStore:
    return SupabaseMetricsStore()


def compute_metrics(campaign_id: UUID, *, store: MetricsStore | None = None, now: datetime | None = None) -> CampaignMetrics:
    """Results for one campaign, from `recipients`, `events` and `conversions`.

    `store` and `now` are for tests; callers pass only the campaign ID.
    """
    store = store or get_metrics_store()
    now = now or datetime.now(UTC)
    recipients = store.get_recipients(str(campaign_id))
    ids = [r["id"] for r in recipients]
    events = store.get_events(ids, now) if ids else []
    conversions = store.get_conversions(ids, now) if ids else []
    return aggregate(campaign_id, recipients, events, conversions, now)
