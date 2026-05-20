from __future__ import annotations

from typing import Any

from bot.infrastructure.onboarding_db import OnboardingDatabase


class DatabaseStateStore:
    def __init__(self, database: OnboardingDatabase) -> None:
        self.database = database
        self._cache: dict[int, dict[str, Any]] = {}

    def get_user(self, chat_id: int) -> dict[str, Any]:
        if chat_id not in self._cache:
            self._cache[chat_id] = self.database.get_chat_state(chat_id)
        return self._cache[chat_id]

    def save_user(self, chat_id: int, data: dict[str, Any]) -> None:
        self._cache[chat_id] = data
        self.database.save_chat_state(chat_id, data)

    def reset_user(self, chat_id: int) -> None:
        self._cache.pop(chat_id, None)
        self.database.reset_chat_state(chat_id)

    def save_chat_message(
        self,
        *,
        chat_id: int,
        direction: str,
        message_type: str,
        telegram_user_id: int | None = None,
        text: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.database.save_chat_message(
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            direction=direction,
            message_type=message_type,
            text=text,
            payload=payload,
        )
