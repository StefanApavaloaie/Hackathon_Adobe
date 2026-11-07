import json
import logging
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.services.supabase_client import get_supabase
from app.services.llm_client import complete_json, LLMUnavailable
from app.agent.guardrails import validate_variants, compute_max_exposure, enforce_exposure_limit
from app.contracts import PageContent
from app.agent.pages import PAGE_INSTRUCTIONS, fallback_page_content

# Definim interfața de care depindem din fișierele colegului
try:
    from app.contracts import PageContent
    from app.agent.pages import PAGE_INSTRUCTIONS, fallback_page_content
except ImportError:
    # Fallbacks locale în caz că branch-urile nu sunt perfect sincronizate încă
    class PageContent(BaseModel):
        model_config = ConfigDict(extra="forbid")
        headline: str
        subheadline: str
        reasons: list[dict[str, str]]
        objection_response: str
        cta_label: str
    PAGE_INSTRUCTIONS = "Keep it brief, address their specific reasons, no prices or percentages."
    def fallback_page_content(label, feedback):
        return PageContent(headline="Welcome back", subheadline="We missed you", reasons=[], objection_response="Try us again.", cta_label="Renew")

logger = logging.getLogger(__name__)

class VariantSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    offer_id: str
    subject: str
    body_text: str
    page_content: PageContent
    reasoning: str

class StrategySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variants: list[VariantSchema]

async def run_strategy(run_id: UUID) -> None:
    supabase = get_supabase()
    
    # Preia detaliile run-ului și limitele
    run_res = supabase.table("agent_runs").select("limits").eq("id", str(run_id)).execute()
    limits = run_res.data[0].get("limits", {})
    
    # Preia ofertele active
    offers_res = supabase.table("offers").select("*").eq("active", True).execute()
    active_offers = {o["id"]: o for o in offers_res.data}
    if not active_offers:
        raise ValueError("No active offers found in catalog.")
    
    cheapest_offer_id = min(active_offers.values(), key=lambda o: o["percent_off"])["id"]
    
    # Preia cohortele pentru acest run
    cohorts = supabase.table("cohorts").select("*").eq("run_id", str(run_id)).execute().data
    
    variants_by_cohort = {}
    
    for cohort in cohorts:
        # Extragem până la 8 comentarii sample pentru această cohortă
        members = supabase.table("cohort_members").select("customer_id").eq("cohort_id", cohort["id"]).limit(8).execute().data
        cust_ids = [m["customer_id"] for m in members]
        
        sample_comments = []
        if cust_ids:
            customers = supabase.table("customers").select("cancel_comment").in_("id", cust_ids).execute().data
            sample_comments = [c["cancel_comment"] for c in customers if c.get("cancel_comment")]
        
        prompt_msgs = [
            {"role": "system", "content": f"You are a retention marketing strategist. Write 2 win-back message variants (A and B) for the provided cohort. Choose offers from the catalog. {PAGE_INSTRUCTIONS}"},
            {"role": "user", "content": json.dumps({
                "cohort_label": cohort["label"],
                "cohort_summary": cohort["summary"],
                "revenue_at_stake_cents": cohort["mrr_at_stake_cents"],
                "sample_comments": sample_comments,
                "active_offers": list(active_offers.values())
            })}
        ]

        variants = []
        is_fallback = False
        
        # Buclă LLM cu Guardrails Retry
        for attempt in range(2):
            try:
                llm_res = await complete_json("strategy", prompt_msgs, StrategySchema, run_id)
                generated_variants = [v.model_dump() for v in llm_res.variants]
                
                # Validăm strict output-ul
                errors = validate_variants(generated_variants, limits, active_offers)
                if not errors:
                    variants = generated_variants
                    break
                
                logger.warning(f"Guardrail errors on attempt {attempt}: {errors}")
                prompt_msgs.extend([
                    {"role": "assistant", "content": json.dumps({"variants": generated_variants})},
                    {"role": "user", "content": f"Your output violated business rules: {errors}. Fix them and try again."}
                ])
                
            except LLMUnavailable:
                logger.warning("LLM Unavailable during strategy step.")
                break

        # Fallback dacă a eșuat de 2 ori sau LLM e picat
        if not variants:
            logger.error(f"Using fallback variants for cohort {cohort['id']}")
            is_fallback = True
            base_page = fallback_page_content(cohort["label"], None).model_dump()
            variants = [
                {
                    "label": "A", "offer_id": cheapest_offer_id, "subject": "We miss you", 
                    "body_text": "Come back and see what's new.", "page_content": base_page, "reasoning": "Fallback used."
                },
                {
                    "label": "B", "offer_id": cheapest_offer_id, "subject": "Give us another try", 
                    "body_text": "We have improved based on feedback.", "page_content": base_page, "reasoning": "Fallback used."
                }
            ]
        
        for v in variants:
            v["is_fallback"] = is_fallback
        variants_by_cohort[cohort["id"]] = variants

    # Validare pe tot run-ul: max exposure
    max_limit = limits.get("max_exposure_cents", 500000)
    final_variants, computed_exposure = enforce_exposure_limit(cohorts, variants_by_cohort, active_offers, max_limit, cheapest_offer_id)

    # 3. Propose step - Inserare în baza de date
    campaign_data = {
        "run_id": str(run_id),
        "status": "draft",
        "max_exposure_cents": computed_exposure
    }
    camp_res = supabase.table("campaigns").insert(campaign_data).execute()
    campaign_id = camp_res.data[0]["id"]
    
    supabase.table("agent_runs").update({"campaign_id": campaign_id}).eq("id", str(run_id)).execute()

    variants_to_insert = []
    for cohort_id, var_list in final_variants.items():
        for v in var_list:
            v["campaign_id"] = campaign_id
            v["cohort_id"] = cohort_id
            variants_to_insert.append(v)
            
    supabase.table("variants").insert(variants_to_insert).execute()