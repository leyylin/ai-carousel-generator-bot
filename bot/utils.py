from __future__ import annotations

import html
import re

from bot.constants import DEFAULT_HANDLE, THEMES
from database.models import User, utcnow
from services.errors import (
    ImageGenerationError,
    LLMError,
    ProviderNotConfigured,
    RendererError,
)
from services.llm.models import CarouselContent

EM_RE = re.compile(r"<em>(.*?)</em>", re.IGNORECASE | re.DOTALL)
HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def truncate(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def rich_title(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    parts: list[str] = []
    position = 0
    for match in EM_RE.finditer(text):
        parts.append(esc(text[position : match.start()]))
        inner = match.group(1).strip()
        if inner:
            parts.append(f"<em>{esc(inner)}</em>")
        position = match.end()
    parts.append(esc(text[position:]))
    result = "".join(parts).strip()
    if "<em>" not in result and result:
        head, separator, tail = result.rpartition(" ")
        if separator and head:
            result = f"{head} <em>{tail}</em>"
        else:
            result = f"<em>{result}</em>"
    return result


def normalize_user_title(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text, flags=re.DOTALL)
    if "<em>" not in text.lower():
        head, separator, tail = text.rpartition(" ")
        text = f"{head} <em>{tail}</em>" if separator and head else f"<em>{text}</em>"
    return text


def clean_handle(raw: str) -> str:
    return (raw or "").strip().lstrip("@").strip()


def is_valid_handle(handle: str) -> bool:
    return bool(HANDLE_RE.fullmatch(handle))


def display_handle(handle: str | None) -> str:
    value = clean_handle(handle or "")
    return f"@{value}" if value else DEFAULT_HANDLE


def format_subscription(user: User) -> str:
    if user.subscription_until and user.subscription_until > utcnow():
        return f"активна до {user.subscription_until.strftime('%d.%m.%Y')}"
    return "нет"


def format_preview(content: CarouselContent, niche_title: str, theme: str) -> str:
    lines = [
        "<b>Предпросмотр карусели</b>",
        f"Ниша: {esc(niche_title)}",
        f"Тема: {esc(truncate(content.topic or '—', 140))}",
        f"Шаблон: {esc(THEMES.get(theme, theme))}",
        "",
    ]
    total = len(content.slides)
    for index, slide in enumerate(content.slides, start=1):
        lines.append(f"<b>{index}. {esc(slide.badge or 'СЛАЙД')}</b>")
        lines.append(rich_title(slide.title))
        if slide.subtitle:
            lines.append(esc(truncate(slide.subtitle, 180)))
        if slide.body:
            lines.append(esc(truncate(slide.body, 240)))
        if slide.highlight_box:
            lines.append(f"<i>{esc(truncate(slide.highlight_box, 180))}</i>")
        if slide.cta_button and index in (1, total):
            lines.append(f"Кнопка: {esc(slide.cta_button)}")
        lines.append("")
    text = "\n".join(lines).strip()
    if len(text) > 3900:
        cut = text.rfind("\n", 0, 3890)
        text = text[: cut if cut > 0 else 3890].rstrip() + "\n\n…"
    return text


def paywall_text(price_stars: int, generations: int, days: int) -> str:
    return (
        "<b>Лимит генераций исчерпан</b>\n\n"
        f"Подписка на {days} дней: <b>{price_stars} ⭐</b>\n"
        f"В неё входит <b>{generations}</b> генераций каруселей.\n\n"
        "Оплата проходит через Telegram Stars."
    )


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, ProviderNotConfigured):
        return (
            "Платный AI-провайдер не настроен. "
            "Проверьте ключи в .env или переключите режим на free."
        )
    if isinstance(exc, LLMError):
        return "AI не смог подготовить текст. Попробуйте ещё раз или измените тему."
    if isinstance(exc, ImageGenerationError):
        return "Не удалось сгенерировать изображения. Попробуйте пересобрать карусель."
    if isinstance(exc, RendererError):
        return "Ошибка рендера слайдов. Проверьте установку Chromium для Playwright."
    return "Что-то пошло не так. Попробуйте ещё раз."
