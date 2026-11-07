# Owned by feature/delivery.
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.errors import not_implemented

router = APIRouter(prefix="/api/campaigns", tags=["sending"], dependencies=[Depends(require_user)])


@router.post("/{campaign_id}/approve")
async def approve_campaign(campaign_id: UUID):
    not_implemented()


@router.get("/{campaign_id}/results")
async def get_results(campaign_id: UUID):
    not_implemented()
