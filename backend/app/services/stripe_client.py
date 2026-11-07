from stripe import StripeClient

from app.config import get_settings
from app.errors import ServiceNotConfigured


def get_stripe() -> StripeClient:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ServiceNotConfigured("Stripe is not configured")
    return StripeClient(settings.stripe_secret_key)
