# Owned by feature/agent. Delete each route as you build it, then delete this file.
import uuid

import pytest

from app.simulator import simulate_responses

RUN_ID = str(uuid.uuid4())
CAMPAIGN_ID = str(uuid.uuid4())

AGENT_STUBS = [
    ("POST", "/api/runs"),
    ("GET", f"/api/runs/{RUN_ID}"),
    ("POST", f"/api/runs/{RUN_ID}/resume"),
    ("GET", f"/api/campaigns/{CAMPAIGN_ID}"),
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/reject"),
    ("POST", f"/api/campaigns/{CAMPAIGN_ID}/report"),
    ("GET", "/api/usage"),
]


@pytest.mark.parametrize("method,path", AGENT_STUBS)
def test_agent_routes_are_stubbed(client, method, path):
    assert client.request(method, path).status_code == 501


def test_simulator_placeholder_does_nothing():
    assert simulate_responses(uuid.uuid4()) is None
