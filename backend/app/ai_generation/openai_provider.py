"""Optional OpenAI-compatible provider.

Only used when ``AI_PROVIDER=openai`` and an API key is configured. It targets
the Chat Completions JSON interface, which many providers (OpenAI, Azure,
local servers like Ollama/LM Studio with an OpenAI-compatible endpoint) expose,
so ``AI_BASE_URL`` can point at a local model too.

Security notes:
  * The API key is read from settings (env var), never logged.
  * The model output is parsed as JSON and handed to the same validation as
    every other provider - a misbehaving model cannot bypass it.
  * Do not send real university documents to an external provider without
    authorization (see SECURITY.md).
"""
from __future__ import annotations

import json

import httpx

from app.ai_generation.base import AIProvider, AIProviderError
from app.ai_generation.prompts import build_system_prompt, build_user_prompt
from app.config import Settings
from app.schemas.question import GenerationRequest


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.ai_api_key:
            raise AIProviderError("AI_API_KEY is not configured for the openai provider.")
        self._api_key = settings.ai_api_key
        self._model = settings.ai_model
        self._base_url = settings.ai_base_url.rstrip("/")
        self._timeout = settings.ai_timeout_seconds

    def generate(self, *, source_text: str, request: GenerationRequest) -> list[dict]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": build_system_prompt(request)},
                {"role": "user", "content": build_user_prompt(source_text)},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            # Never leak the key or raw vendor payloads to the caller.
            raise AIProviderError(f"AI request failed: {type(exc).__name__}") from exc
        except (KeyError, IndexError, ValueError) as exc:
            raise AIProviderError("AI response had an unexpected shape.") from exc

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI did not return valid JSON.") from exc

        questions = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(questions, list):
            raise AIProviderError("AI JSON did not contain a 'questions' list.")
        return questions
