import json

from bot.infrastructure.config import Settings, validate_public_https_url
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
                    {"command": "start", "description": "пройти онбординг"},
                    {"command": "routes", "description": "листать мои маршруты"},
                    {"command": "app", "description": "открыть Mini App"},
                    {"command": "restart", "description": "начать заново"},
                    {"command": "debug", "description": "показать Mini App URL"},
                ],
                ensure_ascii=False,
            )
        },
    )

    if settings.miniapp_url:
        validate_public_https_url(settings.miniapp_url)
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

if __name__ == "__main__":
    main()
