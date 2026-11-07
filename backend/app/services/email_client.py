import resend

from app.config import get_settings
from app.errors import ServiceNotConfigured


def get_resend():
    """Returns the configured Resend module. Sends must check RECIPIENT_ALLOWLIST when added."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise ServiceNotConfigured("Resend is not configured")
    resend.api_key = settings.resend_api_key
    return resend


def parse_allowlist(raw: str) -> list[str]:
    """RECIPIENT_ALLOWLIST as lower-case addresses, in order, without blanks or repeats."""
    emails: list[str] = []
    for part in raw.split(","):
        email = part.strip().lower()
        if email and email not in emails:
            emails.append(email)
    return emails
