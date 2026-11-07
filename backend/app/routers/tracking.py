# Owned by feature/delivery. Public routes reached from email links, identified only by token.
from datetime import UTC, datetime
from typing import Protocol

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import Settings, get_settings
from app.delivery.tokens import looks_like_token
from app.services.supabase_client import get_supabase

router = APIRouter(tags=["tracking"])


class TrackingStore(Protocol):
    def get_recipient(self, token: str) -> dict | None: ...
    def add_event(self, recipient_id: str, event_type: str, source: str) -> None: ...
    def unsubscribe_customer(self, customer_id: str, at: datetime) -> bool: ...


class SupabaseTrackingStore:
    def __init__(self, db=None):
        self.db = db or get_supabase()

    def get_recipient(self, token):
        rows = (
            self.db.table("recipients").select("id,customer_id,source").eq("token", token).limit(1).execute().data
        )
        return rows[0] if rows else None

    def add_event(self, recipient_id, event_type, source):
        self.db.table("events").insert({"recipient_id": recipient_id, "type": event_type, "source": source}).execute()

    def unsubscribe_customer(self, customer_id, at):
        """Sets unsubscribed_at only if it's empty. Returns True if this call set it."""
        rows = (
            self.db.table("customers")
            .update({"unsubscribed_at": at.isoformat()})
            .eq("id", customer_id)
            .is_("unsubscribed_at", "null")
            .execute()
            .data
        )
        return bool(rows)


def get_tracking_store() -> TrackingStore:
    return SupabaseTrackingStore()


def _find(store: TrackingStore, token: str) -> dict | None:
    if not looks_like_token(token):
        return None
    return store.get_recipient(token)


def _page(title: str, message: str, status_code: int = 200) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:48px 24px;background:#f6f6f6;font-family:Arial,Helvetica,sans-serif;color:#222">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;text-align:center">
    <h1 style="font-size:22px;margin:0 0 12px">{title}</h1>
    <p style="margin:0;line-height:1.5">{message}</p>
  </div>
</body>
</html>"""
    return HTMLResponse(html, status_code=status_code, headers={"Cache-Control": "no-store"})


NOT_FOUND = ("Link not found", "This link is no longer valid.")


@router.get("/r/{token}")
def track_click(
    token: str,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    store: TrackingStore = Depends(get_tracking_store),
):
    """Records the click and sends the recipient to their personalised page."""
    recipient = _find(store, token)
    if recipient is None:
        return _page(*NOT_FOUND, status_code=404)
    # Recorded after the redirect is sent, to keep the redirect fast.
    background.add_task(store.add_event, recipient["id"], "clicked", recipient["source"])
    return RedirectResponse(
        f"{settings.frontend_origin}/w/{token}", status_code=302, headers={"Cache-Control": "no-store"}
    )


# POST is the one-click unsubscribe that mail apps send (RFC 8058). The body is ignored.
@router.api_route("/u/{token}", methods=["GET", "POST"])
def unsubscribe(token: str, store: TrackingStore = Depends(get_tracking_store)):
    recipient = _find(store, token)
    if recipient is None:
        return _page(*NOT_FOUND, status_code=404)
    if store.unsubscribe_customer(recipient["customer_id"], datetime.now(UTC)):
        store.add_event(recipient["id"], "unsubscribed", recipient["source"])
    return _page("You're unsubscribed", "You won't get any more of these emails.")
