from __future__ import annotations

import asyncio
import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ImageResult:
    data: bytes
    content_type: str
    prompt: str = ""
    seed: int | None = None

    @property
    def data_uri(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.content_type};base64,{encoded}"


class BaseImageProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        raise NotImplementedError

    async def generate_many(self, prompts: list[str]) -> list[ImageResult | None]:
        async def one(prompt: str) -> ImageResult | None:
            try:
                return await self.generate(prompt)
            except Exception as exc:
                logger.warning("Image generation failed for prompt %r: %s", prompt[:80], exc)
                return None

        return list(await asyncio.gather(*(one(prompt) for prompt in prompts)))

    async def close(self) -> None:
        return None
