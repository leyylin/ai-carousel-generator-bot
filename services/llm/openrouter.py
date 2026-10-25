from __future__ import annotations

from config import Settings
from services.errors import ProviderNotConfigured
from services.llm.openai_compatible import OpenAICompatibleLLM


class OpenRouterProvider(OpenAICompatibleLLM):
    def __init__(self, settings: Settings) -> None:
        if not settings.OPENROUTER_API_KEY:
            raise ProviderNotConfigured(
                "OPENROUTER_API_KEY не задан. Укажите ключ или переключите AI_MODE=free."
            )
        super().__init__(
            endpoint=settings.OPENROUTER_ENDPOINT,
            model=settings.OPENROUTER_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            timeout=settings.LLM_TIMEOUT,
            retries=settings.LLM_RETRIES,
            extra_headers={
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": "AI Carousel Generator Bot",
            },
        )
