from __future__ import annotations

from config import Settings
from services.errors import ProviderNotConfigured
from services.image_gen.base import BaseImageProvider
from services.image_gen.free import FreePollinationsProvider
from services.image_gen.huggingface import HuggingFaceImageProvider
from services.image_gen.local_sd import LocalSDImageProvider
from services.image_gen.paid import FalImageProvider


def build_image_provider(settings: Settings) -> BaseImageProvider:
    if settings.IMAGE_MODE == "free":
        return FreePollinationsProvider(settings)
    if settings.IMAGE_MODE == "paid":
        return FalImageProvider(settings)
    if settings.IMAGE_MODE == "local":
        return LocalSDImageProvider(
            base_url=settings.FREE_IMAGE_BASE_URL,
            timeout=90,
            retries=2,
        )
    if settings.IMAGE_MODE in {"hf", "huggingface"}:
        if not settings.HF_API_KEY:
            raise ProviderNotConfigured(
                "Для IMAGE_MODE=hf укажите HF_API_KEY в .env "
                "(токен: https://huggingface.co/settings/tokens)"
            )
        return HuggingFaceImageProvider(api_key=settings.HF_API_KEY)
    raise ProviderNotConfigured(f"Неизвестный IMAGE_MODE: {settings.IMAGE_MODE}")
