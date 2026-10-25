from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

router = Router(name="errors")
logger = logging.getLogger(__name__)


@router.errors()
async def on_error(event: ErrorEvent, bot: Bot) -> None:
    exception = event.exception
    logger.error(
        "Unhandled update error: %s",
        exception,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    update = event.update
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(
                "Произошла ошибка. Попробуйте ещё раз или отправьте /start.",
                show_alert=True,
            )
        elif update.message is not None:
            await update.message.answer(
                "Произошла ошибка. Попробуйте ещё раз или отправьте /start."
            )
    except Exception:
        logger.debug("Failed to notify user about error", exc_info=True)
