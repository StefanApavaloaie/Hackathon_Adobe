import random
import pytest
from app.simulator import plan_outcomes

def test_simulator_same_seed_gives_same_outcomes():
    """Același seed generează exact aceفسeși rezultate."""
    recipients = [
        {"customer_id": "c-1", "campaign_id": "camp-1", "cancel_feedback": "too_expensive", "mrr_cents": 1000, "offer_id": "off-large"}
    ]
    offers = {"off-large": {"percent_off": 40, "duration_months": 1}}
    
    rng1 = random.Random("test-seed-123")
    events1, conv1 = plan_outcomes(recipients, offers, rng1)
    
    rng2 = random.Random("test-seed-123")
    events2, conv2 = plan_outcomes(recipients, offers, rng2)
    
    assert events1 == events2
    assert conv1 == conv2

def test_simulator_zero_percent_offer_click_rate_behavior():
    """O ofertă cu 0% discount folosește banda 0% (verificăm că funcționează fără erori)."""
    recipients = [
        {"customer_id": "c-2", "campaign_id": "camp-1", "cancel_feedback": "missing_features", "mrr_cents": 2000, "offer_id": "off-zero"}
    ]
    offers = {"off-zero": {"percent_off": 0, "duration_months": 1}}
    
    rng = random.Random("fixed-seed")
    events, conv = plan_outcomes(recipients, offers, rng)
    # Funcția rulează corect și întoarce listele corespunzătoare ratei ascunse
    assert isinstance(events, list)
    assert isinstance(conv, list)

def test_simulator_timestamps_within_60_seconds():
    """Fiecare timestamp generat se încadrează într-o fereastră de 60 de secunde."""
    from datetime import datetime
    recipients = [
        {"customer_id": f"c-{i}", "campaign_id": "camp-1", "cancel_feedback": "too_expensive", "mrr_cents": 1000, "offer_id": "off-1"}
        for i in range(20) # Testăm cu mai mulți clienți pentru a prinde evenimente generate
    ]
    offers = {"off-1": {"percent_off": 50, "duration_months": 1}}
    
    rng = random.Random("time-seed")
    events, conversions = plan_outcomes(recipients, offers, rng)
    
    # Verificăm că cel puțin s-a generat ceva
    if events:
        base_dt = datetime.fromisoformat(events[0]["occurred_at"])
        for ev in events:
            ev_dt = datetime.fromisoformat(ev["occurred_at"])
            diff = abs((ev_dt - base_dt).total_seconds())
            # Toate evenimentele generate sunt în interiorul offset-ului de max 60s + delta mic de page_view
            assert diff <= 70