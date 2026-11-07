from typing import Any

def validate_variants(variants: list[dict], limits: dict, active_offers: dict[str, dict]) -> list[str]:
    """Validează variantele propuse de LLM conform regulilor stricte de business."""
    errors = []
    
    if len(variants) != 2:
        errors.append(f"Expected exactly 2 variants, got {len(variants)}.")
    
    labels = set(v.get("label") for v in variants)
    if labels != {"A", "B"}:
        errors.append(f"Variants must be labelled exactly 'A' and 'B'. Got labels: {labels}")

    max_percent = limits.get("max_percent_off", 0)

    for v in variants:
        label = v.get("label", "Unknown")
        offer_id = v.get("offer_id")
        subject = v.get("subject", "")
        body = v.get("body_text", "")

        if offer_id not in active_offers:
            errors.append(f"Variant {label}: offer_id '{offer_id}' is not in the active catalog.")
        else:
            offer_pct = active_offers[offer_id]["percent_off"]
            if offer_pct > max_percent:
                errors.append(f"Variant {label}: offer percent {offer_pct}% exceeds limit of {max_percent}%.")
        
        if len(subject) > 80:
            errors.append(f"Variant {label}: subject exceeds 80 characters (got {len(subject)}).")
        
        if len(body) > 1200:
            errors.append(f"Variant {label}: body_text exceeds 1200 characters (got {len(body)}).")
        
        if "http" in body.lower():
            errors.append(f"Variant {label}: body_text must not contain 'http' links.")
            
        if "<" in body:
            errors.append(f"Variant {label}: body_text must not contain HTML tags (found '<').")

    return errors

def compute_max_exposure(cohorts: list[dict], variants_by_cohort: dict[str, list[dict]], active_offers: dict[str, dict]) -> int:
    """Calculează expunerea maximă posibilă (în cenți) pentru întreaga campanie."""
    total_exposure = 0
    for cohort in cohorts:
        mrr = cohort.get("mrr_at_stake_cents", 0)
        variants = variants_by_cohort.get(cohort["id"], [])
        
        cohort_max_exposure = 0
        for v in variants:
            offer = active_offers.get(v["offer_id"])
            if not offer: continue
            
            # exposure = mrr * percent_off * duration_months / 100
            exposure = int(mrr * offer["percent_off"] * offer["duration_months"] / 100)
            if exposure > cohort_max_exposure:
                cohort_max_exposure = exposure
                
        total_exposure += cohort_max_exposure
    return total_exposure

def enforce_exposure_limit(
    cohorts: list[dict], 
    variants_by_cohort: dict[str, list[dict]], 
    active_offers: dict[str, dict], 
    max_exposure_limit: int,
    cheapest_offer_id: str
) -> tuple[dict[str, list[dict]], int]:
    """Dacă expunerea depășește limita, înlocuiește ofertele scumpe cu cea mai ieftină variantă din catalog."""
    current_exposure = compute_max_exposure(cohorts, variants_by_cohort, active_offers)
    
    if current_exposure <= max_exposure_limit:
        return variants_by_cohort, current_exposure

    # Sortăm cohorte descrescător după MRR pentru a tăia expunerea acolo unde doare mai tare
    sorted_cohorts = sorted(cohorts, key=lambda c: c.get("mrr_at_stake_cents", 0), reverse=True)
    
    for cohort in sorted_cohorts:
        cohort_id = cohort["id"]
        for v in variants_by_cohort.get(cohort_id, []):
            if v["offer_id"] != cheapest_offer_id:
                v["offer_id"] = cheapest_offer_id
                v["reasoning"] = v.get("reasoning", "") + " [Offer downgraded by system to enforce max exposure limit.]"
        
        current_exposure = compute_max_exposure(cohorts, variants_by_cohort, active_offers)
        if current_exposure <= max_exposure_limit:
            break
            
    return variants_by_cohort, current_exposure