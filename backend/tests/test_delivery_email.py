# Owned by feature/delivery.
import pytest

from app.delivery.email_templates import build_email, first_name
from app.services import email_client
from app.services.email_client import EmailNotAllowed, is_allowed, send_email

CLICK = "https://api.example.com/r/tok123"
UNSUB = "https://api.example.com/u/tok123"


def make_email(**overrides):
    params = {
        "name": "Ana Popescu",
        "subject": "We kept your seat warm",
        "body_text": "We heard pricing was tight.\n\nHere's 25% off.",
        "click_url": CLICK,
        "unsubscribe_url": UNSUB,
    }
    params.update(overrides)
    return build_email(**params)


def test_first_name_falls_back_to_there():
    assert first_name("Ana Popescu") == "Ana"
    assert first_name("  ") == "there"
    assert first_name(None) == "there"


def test_email_greets_by_first_name_in_both_versions():
    email = make_email()
    assert "Hi Ana," in email.html
    assert email.text.startswith("Hi Ana,")


def test_email_escapes_html_in_body_and_name():
    email = make_email(name="<b>Eve</b>", body_text='<script>alert("x")</script> & more')
    assert "<script>" not in email.html
    assert "&lt;script&gt;" in email.html
    assert "&amp; more" in email.html
    assert "<b>Eve</b>" not in email.html


def test_email_includes_click_and_unsubscribe_links_in_both_versions():
    email = make_email()
    for version in (email.html, email.text):
        assert CLICK in version
        assert UNSUB in version


def test_email_sets_one_click_list_unsubscribe_headers():
    assert make_email().headers == {
        "List-Unsubscribe": f"<{UNSUB}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def test_subject_has_no_line_breaks():
    assert make_email(subject="Hello\r\nBcc: x@evil.com").subject == "Hello Bcc: x@evil.com"


def test_is_allowed_compares_in_lower_case():
    assert is_allowed(" Ana@Team.dev ", ["ana@team.dev"])
    assert not is_allowed("eve@evil.com", ["ana@team.dev"])
    assert not is_allowed("ana@team.dev", [])


class FakeResend:
    def __init__(self):
        self.sent = []
        self.Emails = self

    def send(self, params, options=None):
        self.sent.append((params, options))
        return {"id": "msg_123"}


@pytest.fixture
def fake_resend(monkeypatch, make_settings):
    resend = FakeResend()
    settings = make_settings(
        resend_api_key="re_test", email_from="Winback <hi@team.dev>", recipient_allowlist="ana@team.dev"
    )
    monkeypatch.setattr(email_client, "get_settings", lambda: settings)
    monkeypatch.setattr(email_client, "get_resend", lambda: resend)
    return resend


def send(to):
    email = make_email()
    return send_email(
        to=to, subject=email.subject, html=email.html, text=email.text, headers=email.headers, idempotency_key="k1"
    )


def test_send_email_refuses_addresses_not_on_the_allowlist(fake_resend):
    with pytest.raises(EmailNotAllowed):
        send("eve@evil.com")
    assert fake_resend.sent == []


def test_send_email_sends_html_and_text_from_email_from(fake_resend):
    assert send("ANA@team.dev") == "msg_123"
    [(params, options)] = fake_resend.sent
    assert params["from"] == "Winback <hi@team.dev>"
    assert params["to"] == ["ANA@team.dev"]
    assert params["html"] and params["text"]
    assert params["headers"]["List-Unsubscribe"] == f"<{UNSUB}>"
    assert options == {"idempotency_key": "k1"}
