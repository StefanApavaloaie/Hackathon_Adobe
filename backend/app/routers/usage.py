# Owned by feature/agent.
from fastapi import APIRouter, Depends

from app.auth import require_user
from app.errors import not_implemented

router = APIRouter(prefix="/api/usage", tags=["usage"], dependencies=[Depends(require_user)])


@router.get("")
async def get_usage():
    not_implemented()
