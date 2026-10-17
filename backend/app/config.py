"""Environment-based configuration.

All secrets and environment-specific values come from environment variables
(or a local ``.env`` file). Nothing sensitive is hard-coded. See ``.env.example``
for the full list of settings.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 60
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
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
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


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used as a FastAPI dependency."""
    return Settings()
