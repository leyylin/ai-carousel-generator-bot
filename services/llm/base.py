from __future__ import annotations

from abc import ABC, abstractmethod

from services.llm.models import CarouselContent


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_carousel(
        self,
        topic: str,
        niche_title: str,
        niche_hint: str,
        slides_count: int,
    ) -> CarouselContent:
        raise NotImplementedError

    async def close(self) -> None:
        return None
