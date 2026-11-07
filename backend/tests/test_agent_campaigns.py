import uuid
from unittest.mock import MagicMock
import pytest

def test_reject_campaign_success(client, monkeypatch):
    """Respingerea unei campanii in starea 'draft' returneaza 200 OK."""
    fake_camp_id = str(uuid.uuid4())
    
    mock_db = MagicMock()
    # Simulăm campania găsită ca fiind "draft"
    mock_db.table().select().eq().execute.return_value.data = [{"status": "draft"}]
    monkeypatch.setattr("app.routers.campaigns.get_supabase", lambda: mock_db)
    
    response = client.post(f"/api/campaigns/{fake_camp_id}/reject")
    
    assert response.status_code == 200
    assert "rejected successfully" in response.json()["message"]
    # Verificăm că update-ul a fost apelat cu "rejected"
    mock_db.table().update.assert_called_with({"status": "rejected"})

def test_reject_campaign_409_not_draft(client, monkeypatch):
    """Dacă statusul este altul decât draft (ex: approved), primim 409 Conflict."""
    fake_camp_id = str(uuid.uuid4())
    
    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = [{"status": "approved"}]
    monkeypatch.setattr("app.routers.campaigns.get_supabase", lambda: mock_db)
    
    response = client.post(f"/api/campaigns/{fake_camp_id}/reject")
    
    assert response.status_code == 409
    assert "Only draft campaigns can be rejected" in response.json()["detail"]

def test_reject_campaign_404_unknown(client, monkeypatch):
    """Dacă campania nu există, primim 404."""
    fake_camp_id = str(uuid.uuid4())
    
    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = []
    monkeypatch.setattr("app.routers.campaigns.get_supabase", lambda: mock_db)
    
    response = client.post(f"/api/campaigns/{fake_camp_id}/reject")
    
    assert response.status_code == 404
    assert "Campaign not found" in response.json()["detail"]

class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return type("Result", (), {"data": self._rows})()


class _FakeDB:
    """Returns fixed rows per table, enough for GET /api/campaigns/{id}."""

    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


CAMPAIGN_ID = "dddddddd-0000-4000-8000-000000000001"
RUN_ID = "aaaaaaaa-0000-4000-8000-000000000001"


def _campaign_tables(run_rows):
    return {
        "campaigns": [{"id": CAMPAIGN_ID, "status": "draft", "max_exposure_cents": 301400, "run_id": RUN_ID}],
        "cohorts": [],
        "variants": [],
        "reports": [],
        "agent_runs": run_rows,
    }


def test_get_campaign_returns_the_runs_limits(client, monkeypatch):
    limits = {"max_percent_off": 30, "send_cap": 120, "max_exposure_cents": 250000}
    monkeypatch.setattr("app.routers.campaigns.get_supabase", lambda: _FakeDB(_campaign_tables([{"limits": limits}])))

    response = client.get(f"/api/campaigns/{CAMPAIGN_ID}")

    assert response.status_code == 200
    assert response.json()["campaign"]["limits"] == limits


def test_get_campaign_limits_are_null_when_the_run_has_none(client, monkeypatch):
    monkeypatch.setattr("app.routers.campaigns.get_supabase", lambda: _FakeDB(_campaign_tables([])))

    response = client.get(f"/api/campaigns/{CAMPAIGN_ID}")

    assert response.status_code == 200
    assert response.json()["campaign"]["limits"] is None
