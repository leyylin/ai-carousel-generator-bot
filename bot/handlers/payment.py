from __future__ import annotations

import logging
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import BUSINESS_NAME
from bot.keyboards.inline import profile_kb
from bot.utils import format_subscription
from config import get_settings
from database.crud import add_subscription, register_payment
from database.models import User

router = Router(name="payment")
logger = logging.getLogger(__name__)


async def _send_invoice(bot: Bot, chat_id: int, user: User) -> None:
    settings = get_settings()
    payload = f"sub:{user.telegram_id}:{uuid4().hex}"
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"{BUSINESS_NAME} — подписка",
        description=(
            f"Подписка на {settings.SUB_DAYS} дней и "
            f"{settings.SUB_GENERATIONS_LIMIT} генераций каруселей."
        ),
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label=f"Подписка на {settings.SUB_DAYS} дней",
                amount=settings.SUB_PRICE_STARS,
            )
        ],
        start_parameter="carousel-subscription",
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, user: User) -> None:
    await _send_invoice(message.bot, message.chat.id, user)


@router.callback_query(F.data == "subscribe")
async def cb_subscribe(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    await _send_invoice(callback.bot, chat_id, user)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    payload = query.invoice_payload or ""
    if payload.startswith("sub:"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Некорректный платёж")


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    if not (payment.invoice_payload or "").startswith("sub:"):
        logger.warning("Unexpected payment payload: %s", payment.invoice_payload)
        return
    settings = get_settings()
    charge_id = (
        payment.telegram_payment_charge_id
        or payment.provider_payment_charge_id
        or f"unknown:{payment.invoice_payload}"
    )
    registered = await register_payment(
        session=session,
        telegram_id=user.telegram_id,
        charge_id=charge_id,
        amount=payment.total_amount,
        payload=payment.invoice_payload or "",
    )
    if not registered:
        await message.answer("Этот платёж уже был обработан.")
        return
    await add_subscription(
        session=session,
        user=user,
        days=settings.SUB_DAYS,
        generations=settings.SUB_GENERATIONS_LIMIT,
    )
    await session.refresh(user)
    await message.answer(
        "<b>✅ Подписка активирована</b>\n\n"
        f"Начислено <b>{settings.SUB_GENERATIONS_LIMIT}</b> генераций.\n"
        f"Статус: <b>{format_subscription(user)}</b>\n\n"
        "Можно создавать новую карусель.",
        reply_markup=profile_kb(),
    )
