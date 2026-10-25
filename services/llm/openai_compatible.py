from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import aiohttp

from services.errors import LLMError
from services.llm.base import BaseLLMProvider
from services.llm.models import CarouselContent
from services.llm.prompts import build_messages

logger = logging.getLogger(__name__)


class _HTTPStatusError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:300]}")


class OpenAICompatibleLLM(BaseLLMProvider):
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = "",
        timeout: int = 90,
        retries: int = 2,
        extra_headers: dict[str, str] | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.extra_headers = extra_headers or {}
        self.reasoning_effort = reasoning_effort
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
                            "Accept": "application/json",
                        },
                    )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def generate_carousel(
        self,
        topic: str,
        niche_title: str,
        niche_hint: str,
        slides_count: int,
    ) -> CarouselContent:
        messages = build_messages(topic, niche_title, niche_hint, slides_count)
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Exception | None = None
        use_json_mode = True
        attempts = self.retries + 1

        for attempt in range(attempts):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.75,
                "top_p": 0.9,
                "max_tokens": 4096,
                "stream": False,
            }
            if use_json_mode:
                payload["response_format"] = {"type": "json_object"}
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort

            try:
                raw = await self._request(payload, headers)
            except _HTTPStatusError as exc:
                if use_json_mode and exc.status in {400, 404, 422}:
                    use_json_mode = False
                    logger.warning("JSON mode rejected by provider, retrying without it")
                    continue
                last_error = exc
                logger.warning("LLM HTTP error on attempt %s: %s", attempt + 1, exc)
                if attempt < attempts - 1:
                    if exc.status in {402, 429}:
                        delay = 31
                    elif exc.status >= 500:
                        delay = 10
                    else:
                        delay = 1.5 * (attempt + 1)
                    await asyncio.sleep(delay)
                continue
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = exc
                logger.warning("LLM network error on attempt %s: %s", attempt + 1, exc)
                if attempt < attempts - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                continue

            try:
                content = self._extract_content(raw)
                data = self._extract_json(content)
                normalized = self._normalize_payload(data)
                return CarouselContent.model_validate(normalized)
            except Exception as exc:
                last_error = exc
                logger.warning("LLM returned invalid JSON on attempt %s: %s", attempt + 1, exc)
                if attempt < attempts - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))

        raise LLMError(f"Не удалось получить корректный ответ от LLM: {last_error}")

    async def _request(self, payload: dict[str, Any], headers: dict[str, str]) -> str:
        session = await self._ensure_session()
        async with session.post(self.endpoint, json=payload, headers=headers) as response:
            body = await response.text()
            if response.status >= 400:
                raise _HTTPStatusError(response.status, body)
            return body

    @staticmethod
    def _extract_content(raw: str) -> str:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if not isinstance(data, dict):
            return raw
        if "slides" in data:
            return json.dumps(data, ensure_ascii=False)
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                content = "".join(parts)
            if content:
                return str(content)
        if isinstance(data.get("content"), str):
            return data["content"]
        return raw

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("В ответе LLM не найден JSON-объект")
        return json.loads(cleaned[start : end + 1])

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("carousel"), dict):
            payload = payload["carousel"]
        slides = payload.get("slides")
        if isinstance(slides, dict):
            def sort_key(key: str):
                try:
                    return (0, int(key))
                except (TypeError, ValueError):
                    return (1, str(key))

            ordered_keys = sorted(slides.keys(), key=sort_key)
            slides = [slides[key] for key in ordered_keys]
        if not isinstance(slides, list):
            raise LLMError("В JSON отсутствует массив slides")
        if len(slides) < 5:
            raise LLMError(f"LLM вернул {len(slides)} слайдов вместо 5–7")
        payload = {**payload, "slides": slides[:7]}
        payload.setdefault("topic", "")
        payload.setdefault("niche", "")
        return payload
