from __future__ import annotations

from config import Settings
from services.errors import ProviderNotConfigured
from services.llm.base import BaseLLMProvider
from services.llm.free import FreeLLMProvider
from services.llm.openrouter import OpenRouterProvider


def build_llm_provider(settings: Settings) -> BaseLLMProvider:
    if settings.AI_MODE == "free":
        return FreeLLMProvider(settings)
    if settings.AI_MODE == "paid":
        return OpenRouterProvider(settings)
    raise ProviderNotConfigured(f"Неизвестный AI_MODE: {settings.AI_MODE}")
