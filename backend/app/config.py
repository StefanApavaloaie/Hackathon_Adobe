from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """All service keys are optional so the app can start before they exist."""

    # hide_input_in_errors keeps rejected secrets out of startup logs.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True)

    frontend_origin: str = "http://localhost:5173"

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    llm_mode: Literal["saved", "live"] = "saved"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    resend_api_key: str = ""
    recipient_allowlist: str = ""

    @field_validator("frontend_origin")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("stripe_secret_key")
    @classmethod
    def require_stripe_test_key(cls, value: str) -> str:
        if value and not value.startswith("sk_test_"):
            raise ValueError("STRIPE_SECRET_KEY must begin with sk_test_")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
