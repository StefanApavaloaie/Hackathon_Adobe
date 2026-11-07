from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage():
    not_implemented()
