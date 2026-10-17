"""Provider selection. The rest of the app calls get_provider() and never
needs to know which concrete provider is active."""
from __future__ import annotations

from app.ai_generation.base import AIProvider, AIProviderError
from app.ai_generation.mock_provider import MockAIProvider
from app.config import Settings


def get_provider(settings: Settings) -> AIProvider:
    provider = (settings.ai_provider or "mock").lower()
    if provider == "mock":
        return MockAIProvider()
    if provider == "openai":
        # Imported lazily so the app works without httpx-reachable networks and
        # so a missing optional dependency never breaks the mock path.
        from app.ai_generation.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    raise AIProviderError(f"Unknown AI_PROVIDER: {provider!r}")
