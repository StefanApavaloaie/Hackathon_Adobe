import logging
from uuid import UUID
from app.services.supabase_client import get_supabase
# from app.stripe_import import import_customers # Va fi implementat de branch-ul delivery
from app.agent.diagnose import run_diagnose
from app.agent.strategy import run_strategy


logger = logging.getLogger(__name__)

def _delete_proposal(supabase, run_id: UUID) -> None:
    """Delete this run's campaign and its variants, so the step is safe to repeat."""
    campaigns = supabase.table("campaigns").select("id").eq("run_id", str(run_id)).execute().data
    for camp in campaigns:
        supabase.table("variants").delete().eq("campaign_id", camp["id"]).execute()
    supabase.table("campaigns").delete().eq("run_id", str(run_id)).execute()


async def run_pipeline(run_id: UUID):
    supabase = get_supabase()
    
    def update_state(status: str, step: str = None, error: str = None):
        data = {"status": status}
        if step: data["current_step"] = step
        if error is not None: data["error"] = error
        supabase.table("agent_runs").update(data).eq("id", str(run_id)).execute()

    try:
        # Preluăm starea curentă pentru resume
        run_data = supabase.table("agent_runs").select("current_step").eq("id", str(run_id)).execute().data[0]
        step = run_data["current_step"]

        if step == "import":
            # 1. IMPORT
            # Placeholder pentru conexiunea cu Delivery Branch
            # customers_imported = import_customers() 
            logger.info(f"Run {run_id}: Import completed.")
            step = "diagnose"
            update_state(status="running", step=step)

        if step == "diagnose":
            # 2. DIAGNOSE
            # cohort_members has no run_id: delete by this run's cohort ids.
            # Variants reference cohorts, so clear any earlier proposal first.
            _delete_proposal(supabase, run_id)
            cohort_ids = [c["id"] for c in supabase.table("cohorts").select("id").eq("run_id", str(run_id)).execute().data]
            if cohort_ids:
                supabase.table("cohort_members").delete().in_("cohort_id", cohort_ids).execute()
            supabase.table("cohorts").delete().eq("run_id", str(run_id)).execute()
            
            await run_diagnose(run_id) # AICI E APELUL
            
            logger.info(f"Run {run_id}: Diagnose completed.")
            step = "strategy"
            update_state(status="running", step=step)

        if step == "strategy":
            # 3. STRATEGY & 4. PROPOSE (Sunt combinate în run_strategy)
            # Idempotency cleanup în caz de resume (ștergem variantele și campania veche)
            _delete_proposal(supabase, run_id)
            
            await run_strategy(run_id)
            
            logger.info(f"Run {run_id}: Strategy and Propose completed.")
            step = "propose" # Îl lăsăm doar ca să treacă la awaiting_approval 
            update_state(status="awaiting_approval", step=step)
            
        if step == "propose":
            # Propose is written by run_strategy; reaching here only marks the run ready.
            update_state(status="awaiting_approval")

    except Exception as e:
        logger.error(f"Run {run_id} failed at step {step}: {e}", exc_info=True)
        # Salvam o eroare scurta, fara stack trace
        update_state(status="failed", error=str(e)[:250])