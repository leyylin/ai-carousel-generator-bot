from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp

from config import Settings
from services.errors import ImageGenerationError
from services.image_gen.base import BaseImageProvider, ImageResult

logger = logging.getLogger(__name__)


def sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}:
        return "image/avif"
    return None


class FreePollinationsProvider(BaseImageProvider):
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.FREE_IMAGE_BASE_URL.rstrip("/")
        self.model = settings.FREE_IMAGE_MODEL
        self.width = settings.IMAGE_WIDTH
        self.height = settings.IMAGE_HEIGHT
        self.suffix = settings.IMAGE_SUFFIX
        self.timeout = settings.IMAGE_TIMEOUT
        self.retries = settings.IMAGE_RETRIES
        self._semaphore = asyncio.Semaphore(settings.IMAGE_CONCURRENCY)
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={
                            "User-Agent": "CarouselBot/1.0",
                            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
                        },
                    )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        full_prompt = prompt.strip()
        suffix = self.suffix.strip()
        if suffix and suffix not in full_prompt:
            full_prompt = f"{full_prompt}{self.suffix}"

        last_error: Exception | None = None
        async with self._semaphore:
            for attempt in range(self.retries + 1):
                current_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
                url = f"{self.base_url}/{quote(full_prompt, safe='')}"
                params = {
                    "width": str(self.width),
                    "height": str(self.height),
                    "model": self.model,
                    "nologo": "true",
                    "enhance": "true",
                    "seed": str(current_seed),
                }
                try:
                    session = await self._ensure_session()
                    async with session.get(url, params=params) as response:
                        data = await response.read()
                        if response.status >= 400:
                            content_type = response.content_type or "unknown"
                            if "json" in content_type or "text" in content_type:
                                body = data[:200].decode("utf-8", errors="replace")
                            else:
                                body = f"{content_type}, {len(data)} bytes"
                            raise ImageGenerationError(
                                f"Pollinations HTTP {response.status}: {body}"
                            )
                        mime = sniff_image_mime(data[:32])
                        if mime is None or len(data) < 5_000:
                            raise ImageGenerationError("Pollinations returned an invalid image")
                        return ImageResult(
                            data=data,
                            content_type=mime,
                            prompt=full_prompt,
                            seed=current_seed,
                        )
                except (asyncio.TimeoutError, aiohttp.ClientError, ImageGenerationError) as exc:
                    last_error = exc
                    logger.warning(
                        "Pollinations image attempt %s failed: %s", attempt + 1, exc
                    )
                    if attempt < self.retries:
                        await asyncio.sleep(5.0 * (attempt + 1))

        raise ImageGenerationError(f"Не удалось сгенерировать изображение: {last_error}")
