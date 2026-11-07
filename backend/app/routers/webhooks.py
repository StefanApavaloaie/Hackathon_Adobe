from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook():
    not_implemented()


@router.post("/resend")
async def resend_webhook():
    not_implemented()
