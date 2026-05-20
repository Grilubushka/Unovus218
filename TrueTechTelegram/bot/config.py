"""Конфигурация приложения, читаемая из переменных окружения."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Хранит настройки, необходимые для запуска бота."""

    bot_token: str
    log_level: str = "INFO"
    database_path: str = "data/bot.sqlite3"


def load_settings() -> Settings:
    """Загружает настройки из окружения и явно падает без токена бота."""

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Переменная окружения BOT_TOKEN обязательна для запуска бота.")

    return Settings(
        bot_token=token,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        database_path=os.getenv("DATABASE_PATH", "data/bot.sqlite3").strip() or "data/bot.sqlite3",
    )
