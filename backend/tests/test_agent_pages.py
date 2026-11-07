import pytest
from app.agent.pages import fallback_page_content, PAGE_INSTRUCTIONS
from app.contracts import PageContent

# Listă completă de motive conform limitelor Stripe + scenarii de corner cases
FEEDBACK_REASONS = [
    "too_expensive", "missing_features", "switched_service", 
    "unused", "too_complex", "low_quality", "customer_service", 
    None, "unknown_reason_from_future"
]

@pytest.mark.parametrize("feedback", FEEDBACK_REASONS)
def test_fallback_validates_as_page_content(feedback):
    """Fiecare fallback generat trebuie să fie validat perfect de modelul Pydantic PageContent."""
    content = fallback_page_content("Test Cohort", feedback)
    
    assert isinstance(content, PageContent)
    
    dumped = content.model_dump()
    validated = PageContent(**dumped)
    assert validated.headline == content.headline

@pytest.mark.parametrize("feedback", FEEDBACK_REASONS)
def test_fallback_has_no_prices_or_percentages(feedback):
    """Niciun string returnat în fallback nu trebuie să conțină '%' sau '$'."""
    content = fallback_page_content("Test Cohort", feedback)
    
    text_to_check = [
        content.headline,
        content.subheadline,
        content.objection_response,
        content.cta_label
    ]
    
    # Corecția este aici: folosim NOTAȚIA CU PUNCT (reason_block.title), nu dicționar
    for reason_block in content.reasons:
        text_to_check.append(reason_block.title)
        text_to_check.append(reason_block.body)
        
    full_text = " ".join(text_to_check)
    
    assert "%" not in full_text
    assert "$" not in full_text
    
def test_page_instructions_forbid_money_symbols():
    """Instrucțiunile trimise către LLM trebuie să specifice clar interdicția pentru prețuri/procente."""
    instructions_lower = PAGE_INSTRUCTIONS.lower()
    assert "%" in instructions_lower or "percentage" in instructions_lower
    assert "$" in instructions_lower or "price" in instructions_lower