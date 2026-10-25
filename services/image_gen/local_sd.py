from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import aiohttp

from services.errors import ImageGenerationError
from services.image_gen.base import BaseImageProvider, ImageResult
from services.image_gen.free import sniff_image_mime

logger = logging.getLogger(__name__)


class LocalSDImageProvider(BaseImageProvider):
    def __init__(
        self,
        base_url: str = "https://image.pollinations.ai/prompt",
        timeout: int = 90,
        retries: int = 2,
        min_interval: float = 46.0,
        api_key: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.width = 768
        self.height = 1024
        self.model = "flux"
        self.retry_delay = 2.5
        self.min_interval = max(0.0, min_interval)
        self.api_key = api_key.strip()
        self._next_request_at = 0.0
        self._request_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    headers = {
                        "User-Agent": "CarouselBot/1.0",
                        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
                    }
                    if self.api_key:
                        headers["Authorization"] = f"Bearer {self.api_key}"
                    self._session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers=headers,
                    )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def generate_image(self, prompt: str) -> bytes:
        last_error: Exception | None = None
        loop = asyncio.get_running_loop()

        async with self._request_lock:
            for attempt in range(self.retries + 1):
                delay = self._next_request_at - loop.time()
                if delay > 0:
                    logger.info(
                        "Pollinations rate limit: waiting %.1f s before next image",
                        delay,
                    )
                    await asyncio.sleep(delay)

                self._next_request_at = loop.time() + self.min_interval
                url = f"{self.base_url}/{quote(prompt.strip(), safe='')}"
                params = {
                    "width": str(self.width),
                    "height": str(self.height),
                    "model": self.model,
                    "nologo": "true",
                }
                try:
                    session = await self._ensure_session()
                    async with session.get(url, params=params) as response:
                        data = await response.read()
                        if response.status != 200:
                            detail = self._error_detail(response, data)
                            logger.error(
                                "Pollinations image HTTP %s: %s",
                                response.status,
                                detail,
                            )
                            if response.status in {402, 429}:
                                retry_after = self._retry_after(response)
                                self._next_request_at = max(
                                    self._next_request_at,
                                    loop.time() + retry_after,
                                )
                                last_error = ImageGenerationError(
                                    f"Pollinations image HTTP {response.status}: {detail}"
                                )
                                logger.warning(
                                    "Pollinations free limit reached; waiting %.1f s "
                                    "(attempt %s/%s)",
                                    retry_after,
                                    attempt + 1,
                                    self.retries + 1,
                                )
                                if attempt < self.retries:
                                    continue
                                raise last_error
                            if response.status >= 500 and attempt < self.retries:
                                await asyncio.sleep(self.retry_delay)
                                continue
                            raise ImageGenerationError(
                                f"Pollinations image HTTP {response.status}: {detail}"
                            )

                        mime = sniff_image_mime(data[:32])
                        if mime is None or len(data) < 5_000:
                            logger.warning(
                                "Pollinations returned an invalid image "
                                "(attempt %s/%s, %s bytes)",
                                attempt + 1,
                                self.retries + 1,
                                len(data),
                            )
                            if attempt < self.retries:
                                await asyncio.sleep(self.retry_delay)
                                continue
                            raise ImageGenerationError(
                                "Pollinations вернул некорректное изображение"
                            )
                        return data
                except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                    last_error = exc
                    logger.warning(
                        "Pollinations image request failed "
                        "(attempt %s/%s): %s",
                        attempt + 1,
                        self.retries + 1,
                        exc,
                    )
                    if attempt >= self.retries:
                        break
                    await asyncio.sleep(self.retry_delay)

        raise ImageGenerationError(
            f"Не удалось получить изображение из Pollinations: {last_error}"
        )

    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        data = await self.generate_image(prompt)
        mime = sniff_image_mime(data[:32])
        if mime is None:
            raise ImageGenerationError("Pollinations вернул неизвестный формат")
        return ImageResult(
            data=data,
            content_type=mime,
            prompt=prompt,
            seed=seed,
        )

    def _retry_after(self, response: aiohttp.ClientResponse) -> float:
        raw = response.headers.get("Retry-After", "")
        try:
            return max(1.0, float(raw))
        except (TypeError, ValueError):
            return self.min_interval

    def _error_detail(self, response: aiohttp.ClientResponse, data: bytes) -> str:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "json" in content_type or "text" in content_type:
            text = data[:300].decode("utf-8", errors="replace").strip()
            return text or response.reason or "empty response"
        return f"{response.content_type or 'binary'}, {len(data)} bytes"
