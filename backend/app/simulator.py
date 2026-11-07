# Owned by feature/agent. Keep the name and signature: feature/delivery calls it after sending.
from uuid import UUID


def simulate_responses(campaign_id: UUID) -> None:
    """PLACEHOLDER. Write events and conversions with source='simulated' for the
    campaign's simulated recipients, using hidden rates that the agent never sees.

    Does nothing until implemented.
    """
