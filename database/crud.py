from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Payment, User, utcnow


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
) -> User:
    user = await get_user(session, telegram_id)
    if user is not None:
        if username and user.username != username:
            user.username = username
        return user
    settings = get_settings()
    user = User(
        telegram_id=telegram_id,
        username=username,
        generations_left=settings.FREE_TRIAL_GENERATIONS,
    )
    session.add(user)
    await session.flush()
    return user


async def set_instagram_handle(session: AsyncSession, user: User, handle: str) -> None:
    user.instagram_handle = handle
    await session.flush()


async def set_niche(session: AsyncSession, user: User, niche: str) -> None:
    user.selected_niche = niche
    await session.flush()


async def consume_generation(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.generations_left > 0)
        .values(generations_left=User.generations_left - 1)
    )
    return bool(result.rowcount)


async def refund_generation(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(generations_left=User.generations_left + 1)
    )


async def add_subscription(
    session: AsyncSession,
    user: User,
    days: int,
    generations: int,
) -> None:
    now = utcnow()
    base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
    user.subscription_until = base + timedelta(days=days)
    user.generations_left += generations
    await session.flush()


async def register_payment(
    session: AsyncSession,
    telegram_id: int,
    charge_id: str,
    amount: int,
    payload: str,
) -> bool:
    existing = await session.scalar(select(Payment).where(Payment.charge_id == charge_id))
    if existing is not None:
        return False
    session.add(
        Payment(
            telegram_id=telegram_id,
            charge_id=charge_id,
            amount=amount,
            payload=payload,
        )
    )
    await session.flush()
    return True


def subscription_active(user: User) -> bool:
    return bool(user.subscription_until and user.subscription_until > utcnow())
