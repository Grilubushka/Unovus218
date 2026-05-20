"""Точка входа: позволяет запускать бота командой `python -m bot`."""

import asyncio

from bot.app import main


if __name__ == "__main__":
    # Запускаем асинхронный event loop, который обслуживает Telegram long polling.
    asyncio.run(main())
