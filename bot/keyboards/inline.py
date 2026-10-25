from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import FIELD_LABELS, NICHES, THEMES


def niches_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, info in NICHES.items():
        builder.button(text=info["title"], callback_data=f"niche:{key}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="⭐ Подписка", callback_data="subscribe"),
    )
    return builder.as_markup()


def topic_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✨ Придумать идею автоматически", callback_data="topic:auto")
    builder.button(text="⬅️ К выбору ниши", callback_data="menu:niches")
    builder.adjust(1)
    return builder.as_markup()


def preview_kb(theme: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🎨 Шаблон: {THEMES.get(theme, theme)}",
        callback_data="template:cycle",
    )
    builder.button(text="✏️ Изменить текст слайда", callback_data="edit:menu")
    builder.button(text="✅ Собрать готовую карусель (PNG)", callback_data="build")
    builder.adjust(1)
    return builder.as_markup()


def edit_slides_kb(count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index in range(count):
        builder.button(text=str(index + 1), callback_data=f"edit:slide:{index}")
    builder.adjust(6 if count >= 6 else count)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit:back"))
    return builder.as_markup()


def edit_fields_kb(slide_index: int, fields: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field in fields:
        builder.button(
            text=FIELD_LABELS.get(field, field),
            callback_data=f"edit:field:{slide_index}:{field}",
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit:menu"))
    return builder.as_markup()


def edit_prompt_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Отмена", callback_data="edit:back")
    return builder.as_markup()


def result_kb(theme: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Пересобрать картинки", callback_data="rebuild")
    builder.button(
        text=f"🎨 Сменить дизайн ({THEMES.get(theme, theme)}) и пересобрать",
        callback_data="theme:rebuild",
    )
    builder.button(text="➕ Новая карусель", callback_data="new")
    builder.adjust(1)
    return builder.as_markup()


def paywall_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Купить подписку", callback_data="subscribe")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎠 Создать карусель", callback_data="menu:niches")
    builder.button(text="⭐ Подписка", callback_data="subscribe")
    builder.adjust(1)
    return builder.as_markup()


def back_to_niches_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К выбору ниши", callback_data="menu:niches")
    return builder.as_markup()
