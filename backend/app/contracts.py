# Shared by both branches. Frozen after step 0: change it only through a pull request to main.
from pydantic import BaseModel, ConfigDict


class PageReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class PageContent(BaseModel):
    """Written by feature/agent into variants.page_content, and rendered by feature/delivery.

    Holds wording only. Offer text and prices are added by code from the offers table.
    """

    model_config = ConfigDict(extra="forbid")

    headline: str
    subheadline: str
    reasons: list[PageReason]
    objection_response: str
    cta_label: str
