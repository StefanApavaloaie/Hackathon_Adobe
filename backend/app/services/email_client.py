# Owned by feature/delivery. The one place email leaves the system, so the allow-list is enforced here too.
import resend

from app.config import get_settings
from app.errors import ServiceNotConfigured


class EmailNotAllowed(Exception):
    """The address is not on RECIPIENT_ALLOWLIST, so nothing was sent."""


def get_resend():
    """Returns the configured Resend module."""
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


def is_allowed(email: str, allowlist: list[str]) -> bool:
    return email.strip().lower() in allowlist


def send_email(*, to: str, subject: str, html: str, text: str, headers: dict, idempotency_key: str) -> str:
    """Sends one email through Resend and returns its message ID.

    Refuses any address not on RECIPIENT_ALLOWLIST, whatever the caller checked.
    The idempotency key stops Resend sending twice if a send is retried.
    """
    settings = get_settings()
    if not is_allowed(to, parse_allowlist(settings.recipient_allowlist)):
        raise EmailNotAllowed("Recipient is not on RECIPIENT_ALLOWLIST")
    if not settings.email_from:
        raise ServiceNotConfigured("EMAIL_FROM is not set")
    response = get_resend().Emails.send(
        {
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
            "headers": headers,
        },
        {"idempotency_key": idempotency_key},
    )
    return response["id"]
