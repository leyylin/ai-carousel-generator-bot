from __future__ import annotations

from config import Settings
from services.llm.openai_compatible import OpenAICompatibleLLM


class FreeLLMProvider(OpenAICompatibleLLM):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            endpoint=settings.FREE_LLM_ENDPOINT,
            model=settings.FREE_LLM_MODEL,
            api_key=settings.FREE_LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
            retries=settings.LLM_RETRIES,
            extra_headers={"Referer": settings.OPENROUTER_SITE_URL},
            reasoning_effort="low",
        )
