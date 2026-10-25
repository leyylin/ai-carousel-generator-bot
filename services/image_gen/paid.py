from __future__ import annotations

from config import Settings
from services.errors import ProviderNotConfigured
from services.image_gen.base import BaseImageProvider, ImageResult


class FalImageProvider(BaseImageProvider):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.FAL_KEY

    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        raise ProviderNotConfigured(
            "Fal.ai пока не реализован. Используйте IMAGE_MODE=free или добавьте вызов Fal API."
        )


class ReplicateImageProvider(BaseImageProvider):
    def __init__(self, settings: Settings) -> None:
        self.api_token = settings.REPLICATE_API_TOKEN

    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        raise ProviderNotConfigured(
            "Replicate пока не реализован. Используйте IMAGE_MODE=free или добавьте вызов Replicate API."
        )
