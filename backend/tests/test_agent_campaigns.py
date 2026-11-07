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