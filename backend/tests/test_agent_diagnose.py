import uuid
import pytest
from unittest.mock import MagicMock
from app.agent.diagnose import run_diagnose
from app.services.llm_client import LLMUnavailable

MOCK_CUSTOMERS = [
    {"id": "cust-1", "cancel_comment": "Too expensive", "cancel_feedback": "too_expensive", "mrr_cents": 1000},
    {"id": "cust-2", "cancel_comment": "Missing API", "cancel_feedback": "missing_features", "mrr_cents": 2000},
    {"id": "cust-3", "cancel_comment": None, "cancel_feedback": "switched_service", "mrr_cents": 1500},
    {"id": "cust-4", "cancel_comment": "Bad support", "cancel_feedback": "customer_service", "mrr_cents": 1000}
]

@pytest.fixture
def mock_db(monkeypatch):
    # Folosim o clasă falsă robustă în loc de MagicMock pentru a evita problemele de chaining
    class FakeTable:
        def __init__(self, name):
            self.name = name
            self.inserted_data = []
        
        def select(self, *args, **kwargs): return self
        
        @property
        def not_(self): return self
        
        def is_(self, *args, **kwargs): return self
        
        def insert(self, data):
            self.inserted_data.append(data)
            return self
            
        def execute(self):
            if self.name == "customers":
                return MagicMock(data=MOCK_CUSTOMERS)
            return MagicMock()

    class FakeSupabase:
        def __init__(self):
            self.tables = {}
        def table(self, name):
            if name not in self.tables:
                self.tables[name] = FakeTable(name)
            return self.tables[name]
            
    fake_db = FakeSupabase()
    monkeypatch.setattr("app.agent.diagnose.get_supabase", lambda: fake_db)
    return fake_db

@pytest.mark.anyio
async def test_diagnose_mapping_and_fallbacks(mock_db, monkeypatch):
    run_id = uuid.uuid4()
    
    async def fake_complete_json(step, msgs, schema, r_id, **kwargs):
        if step == "diagnose_discover":
            return schema(cohorts=[
                {"key": "price", "label": "Price", "summary": "Too expensive"},
                {"key": "features", "label": "Features", "summary": "Missing features"}
            ])
        elif step == "diagnose_assign":
            return schema(assignments=[
                {"index": 0, "cohort_key": "price", "confidence": 0.9},
                {"index": 1, "cohort_key": "features", "confidence": 0.8},
                {"index": 2, "cohort_key": "not_a_discovered_key", "confidence": 0.5},
                
            ])
    monkeypatch.setattr("app.agent.diagnose.complete_json", fake_complete_json)

    await run_diagnose(run_id)

    # Verificăm interceptările direct din clasa FakeTable
    inserted_cohorts = mock_db.tables["cohorts"].inserted_data[0]
    inserted_members = mock_db.tables["cohort_members"].inserted_data[0]
    
    assert len(inserted_members) == 4
    
    empty_comment_cust = next(m for m in inserted_members if m["customer_id"] == "cust-3")
    assert empty_comment_cust["assigned_by"] == "fallback"
    
    unknown_key_cust = next(m for m in inserted_members if m["customer_id"] == "cust-4")
    assert unknown_key_cust["assigned_by"] == "fallback"

    valid_cust = next(m for m in inserted_members if m["customer_id"] == "cust-1")
    assert valid_cust["assigned_by"] == "llm"

@pytest.mark.anyio
async def test_diagnose_total_llm_failure_groups_by_fallback(mock_db, monkeypatch):
    run_id = uuid.uuid4()
    
    async def failing_complete(*args, **kwargs):
        raise LLMUnavailable("API down")
    monkeypatch.setattr("app.agent.diagnose.complete_json", failing_complete)

    await run_diagnose(run_id)

    inserted_cohorts = mock_db.tables["cohorts"].inserted_data[0]
    inserted_members = mock_db.tables["cohort_members"].inserted_data[0]
    
    assert all(m["assigned_by"] == "fallback" for m in inserted_members)
    assert len(inserted_cohorts) == 4