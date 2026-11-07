# Owned by feature/agent.
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/api/usage", tags=["usage"], dependencies=[Depends(require_user)])

# Groq free plan, tokens per day for the configured model. Check the Free Plan
# tab on your Groq limits page and correct these if they differ.
DAILY_TOKEN_ALLOWANCE = 200_000
# Kept unused for the live demo run.
DEMO_TOKEN_RESERVE = 60_000


def sum_tokens(calls: list[dict]) -> int:
    """Input plus output tokens across llm_calls rows; missing counts are 0."""
    return sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in calls)


def summarize_usage(
    today_calls: list[dict],
    latest_run_id: str | None,
    latest_run_calls: list[dict],
    run_id: str | None = None,
    run_calls: list[dict] | None = None,
) -> dict:
    today = sum_tokens(today_calls)
    summary = {
        "tokens_today": today,
        "latest_run_id": latest_run_id,
        "latest_run_tokens": sum_tokens(latest_run_calls),
        "daily_allowance": DAILY_TOKEN_ALLOWANCE,
        "reserve": DEMO_TOKEN_RESERVE,
        "remaining_before_reserve": max(DAILY_TOKEN_ALLOWANCE - DEMO_TOKEN_RESERVE - today, 0),
        # Groq's free tier. Real customer volumes would need a paid plan.
        "llm_cost_usd": 0,
    }
    if run_id is not None:
        # One campaign's own run, for the dashboard's cost-vs-value figures.
        summary["run_id"] = run_id
        summary["run_tokens"] = sum_tokens(run_calls or [])
        summary["run_llm_calls"] = len(run_calls or [])
    return summary


@router.get("")
async def get_usage(run_id: UUID | None = None):
    db = get_supabase()
    midnight_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    today_calls = (
        db.table("llm_calls")
        .select("input_tokens, output_tokens")
        .gte("created_at", midnight_utc.isoformat())
        .execute()
        .data
    )

    latest = db.table("agent_runs").select("id").order("started_at", desc=True).limit(1).execute().data
    latest_run_id = latest[0]["id"] if latest else None
    latest_run_calls = (
        db.table("llm_calls").select("input_tokens, output_tokens").eq("run_id", latest_run_id).execute().data
        if latest_run_id
        else []
    )

    run_calls = (
        db.table("llm_calls").select("input_tokens, output_tokens").eq("run_id", str(run_id)).execute().data
        if run_id
        else None
    )

    return summarize_usage(
        today_calls, latest_run_id, latest_run_calls, str(run_id) if run_id else None, run_calls
    )
