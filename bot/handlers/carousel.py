from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaDocument,
    InputMediaPhoto,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import (
    DEFAULT_THEME,
    FIELD_LABELS,
    NICHES,
    THEMES,
    fields_for_slide,
    next_theme,
)
from bot.keyboards.inline import (
    edit_fields_kb,
    edit_prompt_kb,
    edit_slides_kb,
    niches_kb,
    paywall_kb,
    preview_kb,
    result_kb,
    topic_kb,
)
from bot.states import CarouselFlow
from bot.utils import (
    esc,
    format_preview,
    friendly_error,
    normalize_user_title,
    paywall_text,
)
from database.crud import consume_generation, refund_generation, set_niche
from database.models import User
from services.container import Services
from services.llm.models import CarouselContent
from services.renderer.renderer import RenderedSlide

router = Router(name="carousel")
logger = logging.getLogger(__name__)


def _content(data: dict[str, Any]) -> CarouselContent | None:
    raw = data.get("content")
    if not raw:
        return None
    try:
        return CarouselContent.model_validate(raw)
    except Exception:
        return None


def _theme(data: dict[str, Any]) -> str:
    value = data.get("theme") or DEFAULT_THEME
    return value if value in THEMES else DEFAULT_THEME


def _niche_title(data: dict[str, Any], content: CarouselContent | None = None) -> str:
    if data.get("niche_title"):
        return str(data["niche_title"])
    if content is not None and content.niche:
        return content.niche
    info = NICHES.get(data.get("niche", ""), {})
    return info.get("title", "Beauty")


async def _edit_or_send(message: Message, text: str, keyboard) -> None:
    try:
        await message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("niche:"))
async def cb_choose_niche(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    services: Services,
) -> None:
    key = (callback.data or "").split(":", 1)[1]
    info = NICHES.get(key)
    if info is None:
        await callback.answer("Неизвестная ниша", show_alert=True)
        return
    await set_niche(session, user, key)
    await state.set_state(CarouselFlow.waiting_topic)
    await state.update_data(
        niche=key,
        niche_title=info["title"],
        niche_hint=info["hint"],
        theme=DEFAULT_THEME,
        content=None,
    )
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            f"<b>{esc(info['title'])}</b>\n\n"
            "Введите тему поста одним сообщением или нажмите "
            "«Придумать идею автоматически».\n\n"
            f"Например: <i>Почему волосы пушатся после мытья?</i>\n"
            f"Максимум {services.settings.MAX_TOPIC_LENGTH} символов.",
            topic_kb(),
        )


@router.callback_query(F.data == "topic:auto")
async def cb_topic_auto(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    services: Services,
) -> None:
    await callback.answer("Придумываю идею…")
    if callback.message is not None:
        await _generate_preview(callback.message, state, services, user, "")


@router.message(CarouselFlow.waiting_topic, F.text)
async def on_topic(
    message: Message,
    state: FSMContext,
    user: User,
    services: Services,
) -> None:
    topic = (message.text or "").strip()
    if len(topic) < 3:
        await message.answer("Тема слишком короткая. Опишите её подробнее.")
        return
    if len(topic) > services.settings.MAX_TOPIC_LENGTH:
        await message.answer(
            f"Тема слишком длинная. Максимум {services.settings.MAX_TOPIC_LENGTH} символов."
        )
        return
    await _generate_preview(message, state, services, user, topic)


@router.message(CarouselFlow.waiting_topic)
async def on_topic_invalid(message: Message) -> None:
    await message.answer("Отправьте тему текстом или нажмите «Придумать идею».")


async def _generate_preview(
    message: Message,
    state: FSMContext,
    services: Services,
    user: User,
    topic: str,
) -> None:
    data = await state.get_data()
    niche_key = data.get("niche")
    if not niche_key:
        await message.answer("Сначала выберите нишу.", reply_markup=niches_kb())
        return
    info = NICHES.get(niche_key, {"title": "Beauty", "hint": "beauty salon"})
    status = await message.answer("🧠 Генерирую структуру и тексты слайдов…")
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        content = await services.carousel.generate_content(
            topic=topic,
            niche_title=info["title"],
            niche_hint=info["hint"],
            slides_count=services.settings.SLIDES_COUNT,
        )
    except Exception as exc:
        logger.exception("Content generation failed")
        try:
            await status.edit_text(friendly_error(exc))
        except Exception:
            await message.answer(friendly_error(exc))
        return

    theme = _theme(data)
    await state.update_data(
        content=content.model_dump(),
        niche=niche_key,
        niche_title=info["title"],
        niche_hint=info["hint"],
        topic=content.topic,
        theme=theme,
        preview_message_id=status.message_id,
    )
    await state.set_state(CarouselFlow.preview)
    text = format_preview(content, info["title"], theme)
    try:
        await status.edit_text(text, reply_markup=preview_kb(theme))
    except Exception:
        sent = await message.answer(text, reply_markup=preview_kb(theme))
        await state.update_data(preview_message_id=sent.message_id)


@router.callback_query(F.data == "template:cycle")
async def cb_template_cycle(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await callback.answer("Сначала создайте карусель", show_alert=True)
        return
    theme = next_theme(_theme(data))
    await state.update_data(theme=theme)
    await callback.answer(f"Шаблон: {THEMES[theme]}")
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            format_preview(content, _niche_title(data, content), theme),
            preview_kb(theme),
        )


@router.callback_query(F.data == "edit:menu")
async def cb_edit_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await callback.answer("Контент не найден. Начните заново.", show_alert=True)
        return
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            f"<b>Какой слайд изменить?</b>\n\nВсего слайдов: {len(content.slides)}",
            edit_slides_kb(len(content.slides)),
        )


@router.callback_query(F.data.startswith("edit:slide:"))
async def cb_edit_slide(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await callback.answer("Контент не найден", show_alert=True)
        return
    try:
        index = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Некорректный слайд", show_alert=True)
        return
    if index < 0 or index >= len(content.slides):
        await callback.answer("Некорректный слайд", show_alert=True)
        return
    fields = fields_for_slide(index, len(content.slides))
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            f"<b>Слайд {index + 1}</b>\n\nЧто изменить?",
            edit_fields_kb(index, fields),
        )


@router.callback_query(F.data.startswith("edit:field:"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await callback.answer("Контент не найден", show_alert=True)
        return
    parts = (callback.data or "").split(":", 3)
    if len(parts) != 4:
        await callback.answer("Некорректная команда", show_alert=True)
        return
    try:
        index = int(parts[2])
    except ValueError:
        await callback.answer("Некорректный слайд", show_alert=True)
        return
    field = parts[3]
    if index < 0 or index >= len(content.slides):
        await callback.answer("Некорректный слайд", show_alert=True)
        return
    if field not in fields_for_slide(index, len(content.slides)):
        await callback.answer("Это поле нельзя изменить", show_alert=True)
        return

    await state.update_data(edit_index=index, edit_field=field)
    await state.set_state(CarouselFlow.editing_field)
    await callback.answer()
    hint = ""
    if field == "title":
        hint = "\n\nЧтобы выделить слово курсивом, оберните его *звёздочками*."
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            f"<b>Слайд {index + 1} · {FIELD_LABELS.get(field, field)}</b>\n\n"
            f"Отправьте новый текст одним сообщением.{hint}",
            edit_prompt_kb(),
        )


@router.message(CarouselFlow.editing_field, F.text)
async def on_field_text(
    message: Message,
    state: FSMContext,
    services: Services,
) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await state.clear()
        await message.answer("Контент не найден. Начните заново: /start")
        return
    try:
        index = int(data.get("edit_index", -1))
    except (TypeError, ValueError):
        index = -1
    field = str(data.get("edit_field", ""))
    if index < 0 or index >= len(content.slides) or field not in fields_for_slide(
        index, len(content.slides)
    ):
        await state.set_state(CarouselFlow.preview)
        await message.answer("Не удалось определить поле. Вернитесь к предпросмотру.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Отправьте новый текст.")
        return
    limit = 220 if field in {"badge", "title", "subtitle", "cta_button"} else services.settings.MAX_FIELD_LENGTH
    if len(text) > limit:
        await message.answer(f"Слишком длинный текст. Максимум {limit} символов.")
        return

    value = normalize_user_title(text) if field == "title" else text
    content.slides[index] = content.slides[index].model_copy(update={field: value})
    await state.update_data(content=content.model_dump())
    await state.set_state(CarouselFlow.preview)

    theme = _theme(data)
    niche_title = _niche_title(data, content)
    preview_text = format_preview(content, niche_title, theme)
    preview_id = data.get("preview_message_id")
    if preview_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=int(preview_id),
                text=preview_text,
                reply_markup=preview_kb(theme),
            )
            await message.answer("✅ Текст обновлён.")
            return
        except Exception:
            logger.debug("Could not edit preview message", exc_info=True)
    sent = await message.answer(preview_text, reply_markup=preview_kb(theme))
    await state.update_data(preview_message_id=sent.message_id)


@router.message(CarouselFlow.editing_field)
async def on_field_invalid(message: Message) -> None:
    await message.answer("Отправьте новый текст одним сообщением.")


@router.callback_query(F.data == "edit:back")
async def cb_edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await state.clear()
        await callback.answer("Сессия устарела", show_alert=True)
        return
    theme = _theme(data)
    await state.set_state(CarouselFlow.preview)
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            format_preview(content, _niche_title(data, content), theme),
            preview_kb(theme),
        )


@router.callback_query(F.data == "build")
async def cb_build(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    services: Services,
) -> None:
    await callback.answer("Собираю карусель…")
    if callback.message is not None:
        await _build(callback.message, state, session, user, services)


@router.callback_query(F.data == "rebuild")
async def cb_rebuild(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    services: Services,
) -> None:
    await callback.answer("Пересобираю картинки…")
    if callback.message is not None:
        await _build(callback.message, state, session, user, services)


@router.callback_query(F.data == "theme:rebuild")
async def cb_theme_rebuild(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    services: Services,
) -> None:
    data = await state.get_data()
    theme = next_theme(_theme(data))
    await state.update_data(theme=theme)
    await callback.answer(f"Новый шаблон: {THEMES[theme]}")
    if callback.message is not None:
        await _build(callback.message, state, session, user, services)


@router.callback_query(F.data == "new")
async def cb_new(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(
            callback.message,
            f"<b>Новая карусель</b>\n\nОсталось генераций: <b>{user.generations_left}</b>\n\n"
            "Выберите нишу:",
            niches_kb(),
        )


async def _build(
    source_message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    services: Services,
) -> None:
    data = await state.get_data()
    content = _content(data)
    if content is None:
        await source_message.answer("Сначала создайте карусель: /start")
        return
    if data.get("building"):
        await source_message.answer("Карусель уже собирается. Подождите немного.")
        return

    theme = _theme(data)
    niche_title = _niche_title(data, content)
    status = await source_message.answer("🎨 Собираю карусель…")
    consumed = False
    try:
        if not await consume_generation(session, user.id):
            await status.edit_text(
                paywall_text(
                    services.settings.SUB_PRICE_STARS,
                    services.settings.SUB_GENERATIONS_LIMIT,
                    services.settings.SUB_DAYS,
                ),
                reply_markup=paywall_kb(),
            )
            await state.set_state(CarouselFlow.preview)
            return
        consumed = True
        await session.refresh(user)
        await state.set_state(CarouselFlow.building)
        await state.update_data(building=True)

        image_note = (
            "\n\nЛимит Pollinations — 1 изображение каждые 45 секунд, "
            "поэтому это может занять несколько минут."
            if services.settings.IMAGE_MODE == "local"
            else ""
        )
        await status.edit_text(
            f"🖼 Генерирую {len(content.slides)} фоновых изображений…{image_note}"
        )
        images = await services.carousel.generate_images(content)

        await status.edit_text("🧩 Рендерю PNG 1080×1350…")
        rendered = await services.carousel.render(
            content=content,
            images=images,
            theme=theme,
            handle=user.instagram_handle,
        )

        await status.edit_text("📤 Отправляю готовые слайды…")
        await _send_album(
            bot=source_message.bot,
            chat_id=source_message.chat.id,
            rendered=rendered,
            content=content,
            niche_title=niche_title,
            send_mode=services.settings.SEND_MEDIA_MODE,
        )
    except Exception as exc:
        logger.exception("Carousel build failed")
        if consumed:
            await refund_generation(session, user.id)
            await session.refresh(user)
        await state.set_state(CarouselFlow.preview)
        await state.update_data(building=False)
        try:
            await status.edit_text(friendly_error(exc))
        except Exception:
            await source_message.answer(friendly_error(exc))
        return

    await state.set_state(CarouselFlow.result)
    await state.update_data(building=False)
    try:
        await status.edit_text(
            f"✅ Карусель готова. Осталось генераций: <b>{user.generations_left}</b>"
        )
    except Exception:
        pass
    try:
        await source_message.answer(
            "Что дальше?",
            reply_markup=result_kb(theme),
        )
    except Exception:
        logger.debug("Could not send result keyboard", exc_info=True)


async def _send_album(
    bot: Bot,
    chat_id: int,
    rendered: list[RenderedSlide],
    content: CarouselContent,
    niche_title: str,
    send_mode: str,
) -> None:
    caption = (
        f"<b>{esc(content.topic or 'Готовая карусель')}</b>\n"
        f"{esc(niche_title)} · {len(rendered)} слайдов"
    )
    if len(caption) > 1000:
        caption = caption[:990] + "…"

    if send_mode in {"photo", "both"}:
        photos = [
            InputMediaPhoto(
                media=BufferedInputFile(slide.data, filename=slide.filename),
                caption=caption if index == 0 else None,
                parse_mode=ParseMode.HTML if index == 0 else None,
            )
            for index, slide in enumerate(rendered)
        ]
        try:
            await bot.send_media_group(chat_id=chat_id, media=photos)
        except Exception:
            logger.warning("Photo album failed, sending individually", exc_info=True)
            for index, slide in enumerate(rendered):
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=BufferedInputFile(slide.data, filename=slide.filename),
                    caption=caption if index == 0 else None,
                    parse_mode=ParseMode.HTML if index == 0 else None,
                )
        if send_mode == "both":
            await asyncio.sleep(1)

    if send_mode in {"document", "both"}:
        documents = [
            InputMediaDocument(
                media=BufferedInputFile(slide.data, filename=slide.filename),
                caption=caption if index == 0 else None,
                parse_mode=ParseMode.HTML if index == 0 else None,
            )
            for index, slide in enumerate(rendered)
        ]
        try:
            await bot.send_media_group(chat_id=chat_id, media=documents)
        except Exception:
            logger.warning("Document album failed, sending individually", exc_info=True)
            for index, slide in enumerate(rendered):
                await bot.send_document(
                    chat_id=chat_id,
                    document=BufferedInputFile(slide.data, filename=slide.filename),
                    caption=caption if index == 0 else None,
                    parse_mode=ParseMode.HTML if index == 0 else None,
                )


@router.callback_query()
async def cb_unknown(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела. Начните заново: /start", show_alert=True)
