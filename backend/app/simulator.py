import random
from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.services.supabase_client import get_supabase

# ---------------------------------------------------------------------------
# 1. Rate ascunse (Hidden Rates Table)
# ---------------------------------------------------------------------------
# Format: (click_rate, conversion_after_click_rate) per [feedback][offer_band]
# Ofer bands: "0%", "1-15%", "16-30%", "31-50%"
HIDDEN_RATES = {
    "too_expensive": {
        "0%": (0.05, 0.10),
        "1-15%": (0.15, 0.20),
        "16-30%": (0.35, 0.40),
        "31-50%": (0.60, 0.50),
    },
    "missing_features": {
        "0%": (0.50, 0.40),
        "1-15%": (0.30, 0.30),
        "16-30%": (0.20, 0.25),
        "31-50%": (0.10, 0.20),
    },
    "switched_service": {
        "0%": (0.10, 0.10),
        "1-15%": (0.20, 0.25),
        "16-30%": (0.40, 0.45),
        "31-50%": (0.50, 0.55),
    },
    # Fallback generic pentru orice alt motiv
    "default": {
        "0%": (0.10, 0.10),
        "1-15%": (0.20, 0.20),
        "16-30%": (0.30, 0.30),
        "31-50%": (0.40, 0.40),
    }
}

def _get_offer_band(percent_off: int) -> str:
    if percent_off == 0:
        return "0%"
    elif 1 <= percent_off <= 15:
        return "1-15%"
    elif 16 <= percent_off <= 30:
        return "16-30%"
    else:
        return "31-50%"

# ---------------------------------------------------------------------------
# 2. Funcția Pură (Math & Planning)
# ---------------------------------------------------------------------------
def plan_outcomes(recipients: list[dict], offers: dict[str, dict], rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Generează evenimentele și conversiile în mod determinist folosind rng."""
    events = []
    conversions = []
    
    base_time = datetime.now(timezone.utc)

    for rec in recipients:
        feedback = rec.get("cancel_feedback") or "default"
        if feedback not in HIDDEN_RATES:
            feedback = "default"
            
        offer_id = rec.get("offer_id")
        offer = offers.get(offer_id, {"percent_off": 0, "duration_months": 1})
        band = _get_offer_band(offer["percent_off"])
        
        click_rate, conv_rate = HIDDEN_RATES[feedback][band]
        
        customer_id = rec["customer_id"]
        campaign_id = rec["campaign_id"]
        
        # Generăm evenimente doar dacă rand-ul se încadrează în rată
        if rng.random() < click_rate:
            # Spread pe parcursul a 60 de secunde
            offset_sec = rng.randint(0, 60)
            t_event = base_time + timedelta(seconds=offset_sec)
            t_str = t_event.isoformat()
            
            # 1. Clicked
            events.append({
                "campaign_id": campaign_id,
                "customer_id": customer_id,
                "event_type": "clicked",
                "occurred_at": t_str
            })
            
            # 2. Page Viewed (la scurt timp după click)
            events.append({
                "campaign_id": campaign_id,
                "customer_id": customer_id,
                "event_type": "page_viewed",
                "occurred_at": (t_event + timedelta(seconds=rng.randint(1, 5))).isoformat()
            })
            
            # Verificăm conversia după click
            if rng.random() < conv_rate:
                checkout_time = t_event + timedelta(seconds=rng.randint(3, 10))
                events.append({
                    "campaign_id": campaign_id,
                    "customer_id": customer_id,
                    "event_type": "checkout_started",
                    "occurred_at": checkout_time.isoformat()
                })
                
                # Calcul MRR redus
                mrr_cents = rec.get("mrr_cents", 1000)
                discounted_mrr = int(mrr_cents * (100 - offer["percent_off"]) / 100)
                
                conversions.append({
                    "campaign_id": campaign_id,
                    "customer_id": customer_id,
                    "mrr_cents": discounted_mrr,
                    "source": "simulated",
                    "occurred_at": (checkout_time + timedelta(seconds=rng.randint(2, 8))).isoformat()
                })
                
    return events, conversions

# ---------------------------------------------------------------------------
# 3. Interacțiunea cu Baza de Date
# ---------------------------------------------------------------------------
def simulate_responses(campaign_id: UUID) -> None:
    supabase = get_supabase()
    
    # 1. Preluăm campania pentru a ști run_id-ul
    camp_res = supabase.table("campaigns").select("run_id").eq("id", str(campaign_id)).execute()
    if not camp_res.data:
        return
    run_id = camp_res.data[0]["run_id"]
    
    # 2. Preluăm ofertele pentru a afla percent_off
    offers_res = supabase.table("offers").select("*").execute()
    offers = {o["id"]: o for o in offers_res.data}
    
    # 3. Preluăm destinatarii cu source = 'simulated'
    # În schema standard, trimiterile sunt în tabela 'sends' sau asociate variantelor/clienților
    recipients_res = supabase.table("sends").select("customer_id, campaign_id, variant_id, source").eq("campaign_id", str(campaign_id)).eq("source", "simulated").execute()
    recipients = recipients_res.data
    if not recipients:
        return
        
    # Avem nevoie și de detalii despre clienți (cancel_feedback, mrr_cents) și varianta (offer_id)
    # Colectăm customer_ids și variant_ids
    cust_ids = [r["customer_id"] for r in recipients]
    var_ids = [r["variant_id"] for r in recipients]
    
    customers_res = supabase.table("customers").select("id, cancel_feedback, mrr_cents").in_("id", cust_ids).execute()
    customers_map = {c["id"]: c for c in customers_res.data}
    
    variants_res = supabase.table("variants").select("id, offer_id").in_("id", var_ids).execute()
    variants_map = {v["id"]: v for v in variants_res.data}
    
    enriched_recipients = []
    for r in recipients:
        c = customers_map.get(r["customer_id"], {})
        v = variants_map.get(r["variant_id"], {})
        enriched_recipients.append({
            "customer_id": r["customer_id"],
            "campaign_id": r["campaign_id"],
            "cancel_feedback": c.get("cancel_feedback"),
            "mrr_cents": c.get("mrr_cents", 0),
            "offer_id": v.get("offer_id")
        })

    # 4. Idempotency: Verificăm dacă există deja evenimente pentru această campanie
    existing_events = supabase.table("events").select("customer_id").eq("campaign_id", str(campaign_id)).execute().data
    if existing_events:
        # Dacă există deja evenimente, rularea nu adaugă nimic nou (idempotent)
        return

    # 5. Inițializăm RNG bazat pe seed string(campaign_id)
    rng = random.Random(str(campaign_id))
    
    events, conversions = plan_outcomes(enriched_recipients, offers, rng)
    
    # 6. Scriem în baza de date
    if events:
        supabase.table("events").insert(events).execute()
    if conversions:
        supabase.table("conversions").insert(conversions).execute()