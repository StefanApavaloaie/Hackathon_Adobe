from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.auth import require_user
from app.services.supabase_client import get_supabase
from app.agent.orchestrator import run_pipeline

router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(require_user)])

class RunLimits(BaseModel):
    max_percent_off: int = Field(default=40, le=50)
    send_cap: int = Field(default=250)
    max_exposure_cents: int = Field(default=500000)

class RunCreateRequest(BaseModel):
    limits: RunLimits = Field(default_factory=RunLimits)

class RunCreateResponse(BaseModel):
    run_id: UUID

# Groq's free tier allows about 8K tokens a minute, shared by every run. Two runs at once
# each take twice as long, and the slower one can run out of retries and fall back to
# template copy. So only one run works at a time. A run still "running" after this long
# is assumed to have crashed (for example, the backend restarted), so it no longer blocks.
RUN_STALE_AFTER = timedelta(minutes=15)


def find_active_run(supabase, now: datetime | None = None) -> dict | None:
    """The run that is still working, if any, ignoring runs that look crashed."""
    cutoff = (now or datetime.now(timezone.utc)) - RUN_STALE_AFTER
    rows = (
        supabase.table("agent_runs")
        .select("id,started_at,current_step")
        .eq("status", "running")
        .gte("started_at", cutoff.isoformat())
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def ensure_no_active_run(supabase) -> None:
    active = find_active_run(supabase)
    if active:
        step = active.get("current_step") or "starting"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another run is still working (step: {step}). Wait for it to finish, then start a new one.",
        )

@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=RunCreateResponse)
async def create_run(background_tasks: BackgroundTasks, request: RunCreateRequest = RunCreateRequest()):
    supabase = get_supabase()
    ensure_no_active_run(supabase)

    # Inserăm noul run în baza de date
    data = {
        "status": "running",
        "current_step": "import",
        "limits": request.limits.model_dump()
    }
    result = supabase.table("agent_runs").insert(data).execute()
    run_id = UUID(result.data[0]["id"])
    
    # Pornim pipeline-ul asincron
    background_tasks.add_task(run_pipeline, run_id)
    
    return RunCreateResponse(run_id=run_id)

@router.get("/{run_id}")
async def get_run_status(run_id: UUID):
    supabase = get_supabase()
    run_result = supabase.table("agent_runs").select("*").eq("id", str(run_id)).execute()
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Run not found")
        
    run_data = run_result.data[0]
    
    # Extragem cohorte dacă există
    cohorts_result = supabase.table("cohorts").select("label, customer_count, mrr_at_stake_cents").eq("run_id", str(run_id)).execute()
    
    # campaigns.run_id is unique; agent_runs has no campaign_id column
    campaign_rows = supabase.table("campaigns").select("id").eq("run_id", str(run_id)).execute().data
    campaign_id = campaign_rows[0]["id"] if campaign_rows else None

    # Întoarcem payload-ul specificat în cerințe
    return {
        "status": run_data["status"],
        "current_step": run_data["current_step"],
        "error": run_data.get("error"),
        "campaign_id": campaign_id,
        "cohorts": cohorts_result.data
    }

@router.post("/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_run(run_id: UUID, background_tasks: BackgroundTasks):
    supabase = get_supabase()
    run_result = supabase.table("agent_runs").select("status").eq("id", str(run_id)).execute()
    
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if run_result.data[0]["status"] != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed runs can be resumed")
    ensure_no_active_run(supabase)
    
    # Resetăm statusul la running și repornim
    supabase.table("agent_runs").update({"status": "running", "error": None}).eq("id", str(run_id)).execute()
    background_tasks.add_task(run_pipeline, run_id)
    
    return {"message": "Run resumed"}