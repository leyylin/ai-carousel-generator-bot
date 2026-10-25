from __future__ import annotations

import asyncio
import json
import logging

import aiohttp

from services.errors import ImageGenerationError
from services.image_gen.base import BaseImageProvider, ImageResult
from services.image_gen.free import sniff_image_mime

logger = logging.getLogger(__name__)


class HuggingFaceImageProvider(BaseImageProvider):
    BASE_URL = "https://router.huggingface.co/hf-inference/models"
    MAX_ATTEMPTS = 4
    NEGATIVE_PROMPT = "blurry, low quality, distorted, deformed, watermark"
    RATE_LIMIT_DELAY = 15.0
    DEFAULT_LOADING_DELAY = 15.0

    def __init__(
        self,
        api_key: str,
        model_id: str = "stabilityai/stable-diffusion-3-medium-diffusers",
        timeout: int = 60,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            raise ValueError("HF_API_KEY is required for HuggingFaceImageProvider")
        self.api_key = key
        self.model_id = model_id
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"Accept": "image/png,image/jpeg,image/webp,*/*"},
                    )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def generate_image(self, prompt: str) -> bytes:
        url = f"{self.BASE_URL}/{self.model_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {"negative_prompt": self.NEGATIVE_PROMPT},
        }
        last_error: str = "unknown error"

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                session = await self._ensure_session()
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.read()
                        if not data:
                            raise ImageGenerationError(
                                "Hugging Face returned an empty image"
                            )
                        return data

                    if response.status == 503:
                        delay = await self._loading_delay(response)
                        last_error = f"HTTP 503, estimated wait {delay:.1f}s"
                        if attempt >= self.MAX_ATTEMPTS:
                            break
                        logger.warning(
                            "Hugging Face model %s is loading (attempt %s/%s), "
                            "retrying in %.1fs",
                            self.model_id,
                            attempt,
                            self.MAX_ATTEMPTS,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status == 429:
                        await response.read()
                        last_error = "HTTP 429 rate limit"
                        if attempt >= self.MAX_ATTEMPTS:
                            break
                        logger.warning(
                            "Hugging Face rate limit hit (attempt %s/%s), "
                            "retrying in %.0fs",
                            attempt,
                            self.MAX_ATTEMPTS,
                            self.RATE_LIMIT_DELAY,
                        )
                        await asyncio.sleep(self.RATE_LIMIT_DELAY)
                        continue

                    if response.status == 402:
                        detail = await self._error_detail(response)
                        raise ImageGenerationError(
                            "Hugging Face: закончились бесплатные кредиты (HTTP 402). "
                            f"{detail}"
                        )

                    detail = await self._error_detail(response)
                    raise ImageGenerationError(
                        f"Hugging Face HTTP {response.status}: {detail}"
                    )
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt >= self.MAX_ATTEMPTS:
                    break
                delay = 5.0 * attempt
                logger.warning(
                    "Hugging Face request failed (attempt %s/%s): %s; retrying in %.0fs",
                    attempt,
                    self.MAX_ATTEMPTS,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise ImageGenerationError(
            f"Не удалось сгенерировать изображение через Hugging Face: {last_error}"
        )

    async def generate(self, prompt: str, seed: int | None = None) -> ImageResult:
        data = await self.generate_image(prompt)
        mime = sniff_image_mime(data[:32])
        if mime is None:
            raise ImageGenerationError("Hugging Face returned an invalid image")
        return ImageResult(
            data=data,
            content_type=mime,
            prompt=prompt,
            seed=seed,
        )

    async def _loading_delay(self, response: aiohttp.ClientResponse) -> float:
        estimated = self.DEFAULT_LOADING_DELAY
        raw = await response.read()
        if raw:
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, dict):
                value = payload.get("estimated_time")
                if isinstance(value, (int, float)) and value > 0:
                    estimated = float(value)
        return min(max(estimated, 1.0), 60.0)

    async def _error_detail(self, response: aiohttp.ClientResponse) -> str:
        raw = await response.read()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "json" in content_type or "text" in content_type:
            text = raw[:300].decode("utf-8", errors="replace").strip()
            return text or response.reason or "empty response"
        return f"{response.content_type or 'binary'}, {len(raw)} bytes"
