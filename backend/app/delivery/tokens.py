# Owned by feature/delivery.
import re

# Tokens are secrets.token_urlsafe(16): 22 URL-safe characters. Allow some slack,
# and turn away anything else before touching the database.
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def looks_like_token(token: str) -> bool:
    return bool(TOKEN_PATTERN.fullmatch(token))
