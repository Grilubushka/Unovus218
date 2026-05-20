"""Сборка и запуск aiogram-приложения."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.db import Database
from bot.handlers import router


async def main() -> None:
    """Создает бота, подключает роутеры и запускает лонг пол."""

    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    database = Database(settings.database_path)
    await database.connect()
    await database.init_schema()

    dispatcher = Dispatcher(storage=MemoryStorage(), db=database, settings=settings)
    dispatcher.include_router(router)

    logging.getLogger(__name__).info("Telegram bot started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
