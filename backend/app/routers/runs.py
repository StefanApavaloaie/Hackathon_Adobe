from uuid import UUID

from fastapi import APIRouter

from app.errors import not_implemented

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
async def start_run():
    not_implemented()


@router.get("/{run_id}")
async def get_run(run_id: UUID):
    not_implemented()


@router.post("/{run_id}/resume")
async def resume_run(run_id: UUID):
    not_implemented()
