from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import BUSINESS_NAME, EXAMPLE_HANDLE, NICHES
from bot.keyboards.inline import niches_kb, profile_kb
from bot.states import Onboarding
from bot.utils import (
    clean_handle,
    display_handle,
    esc,
    format_subscription,
    is_valid_handle,
)
from config import get_settings
from database.crud import set_instagram_handle
from database.models import User

router = Router(name="start")
logger = logging.getLogger(__name__)


def _main_menu_text(user: User) -> str:
    name = esc(user.username or "мастер")
    niche = NICHES.get(user.selected_niche or "", {}).get("title", "не выбрана")
    return (
        f"<b>{BUSINESS_NAME}</b>\n\n"
        f"Привет, {name}! Я собираю Instagram-карусели для бьюти-мастеров.\n\n"
        f"Instagram: <b>{esc(display_handle(user.instagram_handle))}</b>\n"
        f"Ниша: <b>{esc(niche)}</b>\n"
        f"Осталось генераций: <b>{user.generations_left}</b>\n"
        f"Подписка: <b>{esc(format_subscription(user))}</b>\n\n"
        "Выберите нишу для новой карусели:"
    )


def _profile_text(user: User) -> str:
    niche = NICHES.get(user.selected_niche or "", {}).get("title", "не выбрана")
    return (
        "<b>👤 Профиль</b>\n\n"
        f"Instagram: <b>{esc(display_handle(user.instagram_handle))}</b>\n"
        f"Ниша: <b>{esc(niche)}</b>\n"
        f"Осталось генераций: <b>{user.generations_left}</b>\n"
        f"Подписка: <b>{esc(format_subscription(user))}</b>"
    )


async def _edit_or_send(message: Message, text: str, keyboard) -> None:
    try:
        await message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await message.answer(text, reply_markup=keyboard)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    if not user.instagram_handle:
        settings = get_settings()
        await state.set_state(Onboarding.instagram_handle)
        await message.answer(
            f"<b>Добро пожаловать в {BUSINESS_NAME}</b>\n\n"
            "Я генерирую Instagram-карусели на 5–7 слайдов в PNG 1080×1350.\n\n"
            f"Введите ваш Instagram-ник, например <code>{EXAMPLE_HANDLE}</code>. "
            "Он будет подставляться на слайды.\n\n"
            "Вам начислено бесплатных генераций: "
            f"<b>{settings.FREE_TRIAL_GENERATIONS}</b>."
        )
        return
    await message.answer(_main_menu_text(user), reply_markup=niches_kb())


@router.message(Onboarding.instagram_handle, F.text)
async def on_instagram_handle(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    handle = clean_handle(message.text or "")
    if not is_valid_handle(handle):
        await message.answer(
            "Ник выглядит некорректно. Используйте латиницу, цифры, точку и подчёркивание, "
            f"до 30 символов. Например: <code>{EXAMPLE_HANDLE}</code>."
        )
        return
    await set_instagram_handle(session, user, handle)
    await state.clear()
    await message.answer(
        f"✅ Ник <b>{esc(display_handle(handle))}</b> сохранён.\n\n"
        "Теперь выберите нишу:",
        reply_markup=niches_kb(),
    )


@router.message(Onboarding.instagram_handle)
async def on_instagram_handle_invalid(message: Message) -> None:
    await message.answer(
        f"Отправьте Instagram-ник текстом, например <code>{EXAMPLE_HANDLE}</code>."
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User) -> None:
    await message.answer(_profile_text(user), reply_markup=profile_kb())


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(callback.message, _profile_text(user), profile_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Как это работает</b>\n\n"
        "1. Выберите нишу.\n"
        "2. Введите тему поста или нажмите «Придумать идею».\n"
        "3. Проверьте текст, смените шаблон или отредактируйте слайды.\n"
        "4. Нажмите «Собрать готовую карусель».\n\n"
        "Команды: /start, /profile, /help, /subscribe.\n"
        "Подписка оплачивается через Telegram Stars."
    )


@router.callback_query(F.data == "menu:niches")
async def cb_menu_niches(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is not None:
        await _edit_or_send(callback.message, _main_menu_text(user), niches_kb())
