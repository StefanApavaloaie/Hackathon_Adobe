# Owned by feature/delivery. Keep the model fields and the compute_metrics signature:
# feature/agent's report reads them. Change the models only through a pull request to main.
from uuid import UUID

from pydantic import BaseModel


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


def compute_metrics(campaign_id: UUID) -> CampaignMetrics:
    """PLACEHOLDER. Compute results from `recipients`, `events` and `conversions`.

    Returns zeros until implemented.
    """
    return CampaignMetrics(campaign_id=campaign_id, live=SourceMetrics(), simulated=SourceMetrics())
