# Owned by feature/delivery.
from app.services.supabase_client import get_supabase


class SupabaseStore:
    """Base for the delivery stores. Connects on first query, so a request turned away
    early (a malformed token, say) never needs Supabase."""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = get_supabase()
        return self._db
