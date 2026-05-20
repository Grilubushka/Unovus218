import json
from urllib.parse import urlparse

from bot.infrastructure.config import Settings
from bot.infrastructure.telegram_api import TelegramApi


def main() -> None:
    settings = Settings()
    settings.validate()
    api = TelegramApi(settings.bot_token)
    api._request(
        "setMyCommands",
        {
            "commands": json.dumps(
                [
                    {"command": "start", "description": "собрать профиль и маршрут"},
                    {"command": "roadmap", "description": "показать текущий маршрут"},
                    {"command": "restart", "description": "начать заново"},
                ],
                ensure_ascii=False,
            )
        },
    )

    if settings.miniapp_url:
        validate_miniapp_url(settings.miniapp_url)
        print(f"Configuring Mini App URL: {settings.miniapp_url}")
        api._request(
            "setChatMenuButton",
            {
                "menu_button": json.dumps(
                    {
                        "type": "web_app",
                        "text": "Мой маршрут",
                        "web_app": {"url": settings.miniapp_url},
                    },
                    ensure_ascii=False,
                )
            },
        )

    print("Telegram commands and Mini App menu button configured.")


def validate_miniapp_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "MINIAPP_URL должен быть публичным HTTPS URL, например https://your-domain.ru/"
        )
    forbidden_hosts = {"example.com", "localhost", "127.0.0.1", "0.0.0.0"}
    if parsed.hostname in forbidden_hosts:
        raise RuntimeError(
            f"MINIAPP_URL указывает на служебный адрес {parsed.hostname}. "
            "Укажи реальный публичный HTTPS-домен Mini App."
        )


if __name__ == "__main__":
    main()
