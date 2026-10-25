from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from services.carousel_service import CarouselService
from services.image_gen.base import BaseImageProvider
from services.image_gen.factory import build_image_provider
from services.llm.base import BaseLLMProvider
from services.llm.factory import build_llm_provider
from services.renderer.renderer import CarouselRenderer


@dataclass(slots=True)
class Services:
    settings: Settings
    llm: BaseLLMProvider
    image: BaseImageProvider
    renderer: CarouselRenderer
    carousel: CarouselService

    async def close(self) -> None:
        await self.carousel.close()


def build_services(settings: Settings) -> Services:
    llm = build_llm_provider(settings)
    image = build_image_provider(settings)
    renderer = CarouselRenderer(settings)
    carousel = CarouselService(settings, llm, image, renderer)
    return Services(
        settings=settings,
        llm=llm,
        image=image,
        renderer=renderer,
        carousel=carousel,
    )
