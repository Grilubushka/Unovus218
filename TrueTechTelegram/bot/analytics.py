"""Заглушка аналитики: здесь позже можно подключить Amplitude, PostHog или свою БД."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bot.db import Database

logger = logging.getLogger(__name__)


async def track_event(
    user_id: int,
    event_name: str,
    payload: dict[str, Any] | None = None,
    *,
    db: "Database | None" = None,
    session_id: int | None = None,
) -> None:
    """Фиксирует событие пользовательского сценария без внешней аналитической системы."""

    logger.info(
        "trackEvent user_id=%s event=%s payload=%s",
        user_id,
        event_name,
        payload or {},
    )
    if db is not None:
        await db.save_event(
            user_id=user_id,
            session_id=session_id,
            event_name=event_name,
            payload=payload or {},
        )
