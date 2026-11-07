# Owned by feature/delivery.
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from app.auth import AuthUser, require_user
from app.config import Settings, get_settings
from app.delivery.send import (
    CampaignNotFound,
    CampaignRejected,
    DeliveryStore,
    approve,
    get_delivery_store,
    get_email_sender,
    send_campaign,
)
from app.errors import not_implemented
from app.services.email_client import parse_allowlist

router = APIRouter(prefix="/api/campaigns", tags=["sending"], dependencies=[Depends(require_user)])


@router.post("/{campaign_id}/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_campaign(
    campaign_id: UUID,
    background: BackgroundTasks,
    response: Response,
    user: AuthUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
    store: DeliveryStore = Depends(get_delivery_store),
    sender: Callable[..., str] = Depends(get_email_sender),
) -> dict:
    """Approves a draft and starts sending in the background. Repeating it changes nothing."""
    try:
        current, started = approve(store, str(campaign_id), user.id, datetime.now(UTC))
    except CampaignNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found") from None
    except CampaignRejected:
        raise HTTPException(status.HTTP_409_CONFLICT, "Campaign was rejected") from None

    if started:
        background.add_task(
            send_campaign,
            str(campaign_id),
            store=store,
            sender=sender,
            allowlist=parse_allowlist(settings.recipient_allowlist),
            public_api_url=settings.public_api_url,
        )
    else:
        response.status_code = status.HTTP_200_OK
    return {"campaign_id": str(campaign_id), "status": current}


@router.get("/{campaign_id}/results")
async def get_results(campaign_id: UUID):
    not_implemented()
