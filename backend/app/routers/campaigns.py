from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.agent.report import CampaignNotFound, generate_report
from app.auth import require_user
from app.services.supabase_client import get_supabase

# Owned by feature/agent. Approve and results live in sending.py (feature/delivery).
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"], dependencies=[Depends(require_user)])

@router.get("/{campaign_id}")
async def get_campaign(campaign_id: UUID):
    supabase = get_supabase()
    
    # 1. Preluăm datele campaniei
    camp_res = supabase.table("campaigns").select("*").eq("id", str(campaign_id)).execute()
    if not camp_res.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = camp_res.data[0]
    run_id = campaign["run_id"]
    
    # 2. Preluăm cohortele asociate run_id-ului
    cohorts_res = supabase.table("cohorts").select("*").eq("run_id", run_id).execute()
    
    # Organizăm cohortele într-un dicționar pentru a le atașa variantele ușor
    cohorts_map = {
        c["id"]: {
            "id": c["id"], 
            "label": c["label"], 
            "summary": c["summary"], 
            "customer_count": c["customer_count"],
            "mrr_at_stake_cents": c["mrr_at_stake_cents"],
            "variants": []
        } for c in cohorts_res.data
    }
    
    # 3. Preluăm variantele ȘI ofertele printr-un join PostgREST nativ
    # Folosim "offers(*)" pentru a aduce automat rândul din tabela offers asociat
    variants_res = supabase.table("variants").select("*, offers(*)").eq("campaign_id", str(campaign_id)).execute()
    
    for v in variants_res.data:
        cohort_id = v["cohort_id"]
        if cohort_id in cohorts_map:
            cohorts_map[cohort_id]["variants"].append({
                "id": v["id"],
                "label": v["label"],
                "subject": v["subject"],
                "body_text": v["body_text"],
                "page_content": v["page_content"],
                "reasoning": v["reasoning"],
                "is_fallback": v["is_fallback"],
                "offer": v.get("offers")  # Supabase a populat acest câmp datorită FK-ului
            })
            
    # 4. Preluăm raportul (dacă există)
    report_res = supabase.table("reports").select("*").eq("campaign_id", str(campaign_id)).execute()
    report = report_res.data[0] if report_res.data else None
    
    return {
        "campaign": {
            "id": campaign["id"],
            "status": campaign["status"],
            "max_exposure_cents": campaign["max_exposure_cents"],
            "run_id": run_id
        },
        "cohorts": list(cohorts_map.values()),
        "report": report
    }

@router.post("/{campaign_id}/reject")
async def reject_campaign(campaign_id: UUID):
    supabase = get_supabase()
    
    camp_res = supabase.table("campaigns").select("status").eq("id", str(campaign_id)).execute()
    
    if not camp_res.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if camp_res.data[0]["status"] != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft campaigns can be rejected")
        
    supabase.table("campaigns").update({"status": "rejected"}).eq("id", str(campaign_id)).execute()
    
    return {"message": "Campaign rejected successfully"}

@router.post("/{campaign_id}/report")
async def create_report(campaign_id: UUID):
    """Generate the agent's recommendation on demand. It never runs automatically."""
    try:
        return await generate_report(campaign_id)
    except CampaignNotFound:
        raise HTTPException(status_code=404, detail="Campaign not found")
