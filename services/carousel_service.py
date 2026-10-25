from __future__ import annotations

import logging

from bot.constants import BUSINESS_NAME as BRAND_NAME
from config import Settings
from services.image_gen.base import BaseImageProvider, ImageResult
from services.llm.base import BaseLLMProvider
from services.llm.models import CarouselContent
from services.llm.prompts import build_visual_prompts
from services.renderer.renderer import CarouselRenderer, RenderedSlide

logger = logging.getLogger(__name__)


class CarouselService:
    def __init__(
        self,
        settings: Settings,
        llm: BaseLLMProvider,
        image: BaseImageProvider,
        renderer: CarouselRenderer,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.image = image
        self.renderer = renderer

    async def generate_content(
        self,
        topic: str,
        niche_title: str,
        niche_hint: str,
        slides_count: int,
    ) -> CarouselContent:
        content = await self.llm.generate_carousel(
            topic=topic,
            niche_title=niche_title,
            niche_hint=niche_hint,
            slides_count=slides_count,
        )
        content.niche = content.niche or niche_title
        content.topic = content.topic or topic or "Новая карусель"
        total = len(content.slides)
        prompts = build_visual_prompts(
            total=total,
            niche_hint=niche_hint,
            llm_prompts=[slide.image_prompt for slide in content.slides],
        )
        for slide, prompt in zip(content.slides, prompts, strict=True):
            slide.image_prompt = prompt
        return content

    async def generate_images(self, content: CarouselContent) -> list[ImageResult | None]:
        prompts = [slide.image_prompt for slide in content.slides]
        return await self.image.generate_many(prompts)

    async def render(
        self,
        content: CarouselContent,
        images: list[ImageResult | None],
        theme: str,
        handle: str | None,
    ) -> list[RenderedSlide]:
        return await self.renderer.render_carousel(
            content=content,
            images=images,
            theme=theme,
            handle=handle,
            niche=content.niche,
            brand=BRAND_NAME,
        )

    async def close(self) -> None:
        for name, component in (
            ("llm", self.llm),
            ("image", self.image),
            ("renderer", self.renderer),
        ):
            try:
                await component.close()
            except Exception:
                logger.warning("Failed to close %s", name, exc_info=True)
