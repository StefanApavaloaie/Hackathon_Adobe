# Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import pytest
from pydantic import ValidationError

from app.contracts import PageContent
from app.metrics import CampaignMetrics

VALID_PAGE = {
    "headline": "We fixed what you told us",
    "subheadline": "Exports are now one click",
    "reasons": [{"title": "Faster exports", "body": "Shipped in March."}],
    "objection_response": "Cancel any time.",
    "cta_label": "Come back",
}


def test_page_content_accepts_the_agreed_shape():
    assert PageContent.model_validate(VALID_PAGE).reasons[0].title == "Faster exports"


def test_page_content_rejects_unknown_fields_such_as_prices():
    with pytest.raises(ValidationError):
        PageContent.model_validate({**VALID_PAGE, "price": "$1"})


def test_page_content_requires_every_field():
    with pytest.raises(ValidationError):
        PageContent.model_validate({k: v for k, v in VALID_PAGE.items() if k != "cta_label"})


def test_campaign_metrics_keep_live_and_simulated_separate():
    assert {"live", "simulated"} <= set(CampaignMetrics.model_fields)
