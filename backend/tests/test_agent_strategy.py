import pytest
import uuid
from app.agent.guardrails import validate_variants, compute_max_exposure, enforce_exposure_limit
from app.agent.strategy import VariantSchema, run_strategy
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# The schema sent to Groq: labels are an enum, so strict mode can't invent "Variant A"
# ---------------------------------------------------------------------------

VALID_VARIANT = {
    "label": "A",
    "offer_id": "offer-1",
    "subject": "Come back",
    "body_text": "We miss you.",
    "page_content": {
        "headline": "Welcome back",
        "subheadline": "Pick up where you left off.",
        "reasons": [{"title": "Still here", "body": "Your work is waiting."}],
        "objection_response": "Cancel any time.",
        "cta_label": "Come back",
    },
    "reasoning": "Test.",
}


def test_variant_label_schema_is_an_enum_of_a_and_b():
    assert VariantSchema.model_json_schema()["properties"]["label"]["enum"] == ["A", "B"]


def test_variant_label_rejects_free_text():
    with pytest.raises(ValidationError):
        VariantSchema.model_validate({**VALID_VARIANT, "label": "Variant A"})


def test_variant_label_accepts_a_and_b():
    assert VariantSchema.model_validate(VALID_VARIANT).label == "A"
    assert VariantSchema.model_validate({**VALID_VARIANT, "label": "B"}).label == "B"

# ---------------------------------------------------------------------------
# Teste pentru Funcțiile Pure (Guardrails)
# ---------------------------------------------------------------------------

def test_guardrail_variant_count_and_labels():
    limits = {"max_percent_off": 50}
    offers = {"offer-1": {"percent_off": 10}}
    
    # Prea puține
    errors = validate_variants([{"label": "A", "offer_id": "offer-1"}], limits, offers)
    assert any("exactly 2 variants" in e for e in errors)
    
    # Etichete greșite
    errors = validate_variants([
        {"label": "X", "offer_id": "offer-1"},
        {"label": "Y", "offer_id": "offer-1"}
    ], limits, offers)
    assert any("exactly 'A' and 'B'" in e for e in errors)

def test_guardrail_limits_and_text_rules():
    limits = {"max_percent_off": 20}
    offers = {"offer-1": {"percent_off": 30}} # Ofertă care depășește limita
    
    variants = [
        {"label": "A", "offer_id": "invalid-offer", "subject": "a"*100, "body_text": "Check http://link"},
        {"label": "B", "offer_id": "offer-1", "subject": "Valid", "body_text": "This contains HTML <script>"}
    ]
    
    errors = validate_variants(variants, limits, offers)
    assert any("not in the active catalog" in e for e in errors)
    assert any("exceeds limit of 20%" in e for e in errors)
    assert any("subject exceeds 80 characters" in e for e in errors)
    assert any("must not contain 'http'" in e for e in errors)
    assert any("must not contain HTML tags" in e for e in errors)

def test_exposure_calculation_and_enforcement():
    cohorts = [
        {"id": "coh-1", "mrr_at_stake_cents": 10000},
        {"id": "coh-2", "mrr_at_stake_cents": 5000}
    ]
    offers = {
        "cheap": {"percent_off": 10, "duration_months": 1}, # Exposure factor = 10% * 1 = 0.1
        "expensive": {"percent_off": 50, "duration_months": 2} # Exposure factor = 50% * 2 = 1.0
    }
    variants = {
        "coh-1": [{"offer_id": "expensive"}], # Exp: 10000 * 1.0 = 10000
        "coh-2": [{"offer_id": "expensive"}]  # Exp: 5000 * 1.0 = 5000
    }
    
    # Total exp = 15000
    assert compute_max_exposure(cohorts, variants, offers) == 15000
    
    # Forțăm limita la 12000. Algoritmul trebuie să retrogradeze coh-1 (cea cu MRR mai mare)
    new_variants, new_exposure = enforce_exposure_limit(cohorts, variants, offers, 12000, "cheap")
    
    assert new_exposure < 12000
    assert new_variants["coh-1"][0]["offer_id"] == "cheap"
    assert "downgraded" in new_variants["coh-1"][0]["reasoning"]