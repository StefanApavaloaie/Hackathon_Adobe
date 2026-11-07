from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(tags=["tracking"])


@router.get("/r/{token}")
async def track_click(token: str):
    not_implemented()


@router.get("/u/{token}")
async def unsubscribe(token: str):
    not_implemented()
