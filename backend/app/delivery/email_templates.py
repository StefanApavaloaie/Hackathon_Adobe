# Owned by feature/delivery. Builds the win-back email. Everything from the database is escaped.
from dataclasses import dataclass
from html import escape

DEFAULT_CTA = "See your offer"


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str
    headers: dict


def first_name(name: str | None) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "there"


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _html_paragraphs(body_text: str) -> str:
    paragraphs = [p.strip() for p in body_text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "\n".join(
        f'<p style="margin:0 0 16px">{escape(p).replace(chr(10), "<br>")}</p>' for p in paragraphs
    )


def build_email(
    *, name: str | None, subject: str, body_text: str, click_url: str, unsubscribe_url: str, cta_label: str = DEFAULT_CTA
) -> Email:
    """`body_text` is the agent's plain text, with no greeting or links. We add both."""
    greeting = f"Hi {first_name(name)},"
    html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f6f6f6;font-family:Arial,Helvetica,sans-serif;color:#222">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;font-size:16px;line-height:1.5">
    <p style="margin:0 0 16px">{escape(greeting)}</p>
    {_html_paragraphs(body_text)}
    <p style="margin:24px 0">
      <a href="{escape(click_url, quote=True)}" style="display:inline-block;background:#1a56db;color:#fff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:bold">{escape(cta_label)}</a>
    </p>
  </div>
  <p style="max-width:560px;margin:16px auto 0;font-size:12px;color:#888;text-align:center">
    Don't want these emails? <a href="{escape(unsubscribe_url, quote=True)}" style="color:#888">Unsubscribe</a>
  </p>
</body>
</html>"""
    text = (
        f"{greeting}\n\n{body_text.strip()}\n\n{cta_label}: {click_url}\n\n"
        f"--\nDon't want these emails? Unsubscribe: {unsubscribe_url}\n"
    )
    return Email(
        subject=_single_line(subject),
        html=html,
        text=text,
        headers={"List-Unsubscribe": f"<{unsubscribe_url}>"},
    )
