# Owned by feature/agent. Approve and results live in sending.py (feature/delivery).
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.errors import not_implemented

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"], dependencies=[Depends(require_user)])


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: UUID):
    not_implemented()


@router.post("/{campaign_id}/reject")
async def reject_campaign(campaign_id: UUID):
    not_implemented()


@router.post("/{campaign_id}/report")
async def create_report(campaign_id: UUID):
    not_implemented()
