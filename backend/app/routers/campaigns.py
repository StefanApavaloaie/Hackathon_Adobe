from uuid import UUID

from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: UUID):
    not_implemented()


@router.post("/{campaign_id}/approve")
async def approve_campaign(campaign_id: UUID):
    not_implemented()


@router.post("/{campaign_id}/reject")
async def reject_campaign(campaign_id: UUID):
    not_implemented()


@router.get("/{campaign_id}/results")
async def get_results(campaign_id: UUID):
    not_implemented()


@router.post("/{campaign_id}/report")
async def create_report(campaign_id: UUID):
    not_implemented()
