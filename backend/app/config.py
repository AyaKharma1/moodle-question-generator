"""Environment-based configuration.

All secrets and environment-specific values come from environment variables
(or a local ``.env`` file). Nothing sensitive is hard-coded. See ``.env.example``
for the full list of settings.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "Secure AI Moodle Question Generator"
    environment: str = "development"  # development | production
    debug: bool = False

    # --- Security / auth ---
    # MUST be overridden in production via SECRET_KEY env var.
    secret_key: str = DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 60
    # Set REGISTRATION_OPEN=false once all accounts exist (e.g. on a shared server),
    # so nobody else can create an account.
    registration_open: bool = True
    jwt_algorithm: str = "HS256"

    # --- Database ---
    # Default targets the docker-compose Postgres service. For local unit
    # tests an in-memory SQLite URL is injected instead (see tests/conftest).
    database_url: str = "postgresql+psycopg://moodle:moodle@localhost:5432/moodleqg"

    # --- CORS (frontend dev server) ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- File uploads ---
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB per file
    # Upper bound for one whole request (several XML files at once). Larger
    # requests are refused before the body is read.
    max_request_bytes: int = 120 * 1024 * 1024
    # Upper bound for the sum of all files of one import call.
    max_import_total_bytes: int = 100 * 1024 * 1024
    allowed_extensions: set[str] = Field(
        default_factory=lambda: {".pdf", ".txt", ".docx"}
    )

    # --- AI provider ---
    ai_provider: str = "mock"  # mock | openai
    ai_api_key: str | None = None
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = 60.0
    # Maximum questions allowed per generation call (rate/abuse protection).
    ai_max_questions_per_request: int = 50

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def assert_production_safe(self) -> None:
        """Refuse to start in production with a guessable signing key.

        Anyone who knows SECRET_KEY can forge login tokens, so the default
        value (which is public in this repository) must never be used there.
        """
        if self.is_production and (self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < 32):
            raise RuntimeError(
                "SECRET_KEY ist für ENVIRONMENT=production nicht sicher genug. Bitte einen "
                "zufälligen Wert mit mindestens 32 Zeichen setzen: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used as a FastAPI dependency."""
    return Settings()
