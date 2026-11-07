from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(prefix="/api/pages", tags=["pages"])


@router.get("/{token}")
async def get_page(token: str):
    not_implemented()


@router.post("/{token}/checkout")
async def create_checkout(token: str):
    not_implemented()
