from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import carousel, errors, payment, start
from bot.middlewares import DatabaseMiddleware, ServicesMiddleware
from config import get_settings
from database.session import close_db, get_session_maker, init_db
from services.container import build_services


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)

    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен.")
        sys.exit(1)

    await init_db()
    try:
        services = build_services(settings)
    except Exception as exc:
        logger.error("Не удалось инициализировать провайдеров: %s", exc)
        await close_db()
        sys.exit(1)
    session_maker = get_session_maker()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    database_middleware = DatabaseMiddleware(session_maker)
    services_middleware = ServicesMiddleware(services)
    for observer in (
        dispatcher.message,
        dispatcher.callback_query,
        dispatcher.pre_checkout_query,
    ):
        observer.middleware(database_middleware)
        observer.middleware(services_middleware)

    dispatcher.include_routers(
        payment.router,
        start.router,
        carousel.router,
    )
    dispatcher.errors.register(errors.on_error)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot started")
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await services.close()
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
