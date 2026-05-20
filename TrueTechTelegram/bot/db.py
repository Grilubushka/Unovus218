"""Работа с SQLite: пользователи, сессии теста, ответы и аналитические события."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import aiosqlite
from aiogram.types import User


class Database:
    """Тонкая обертка над SQLite, чтобы хендлеры не знали SQL-детали."""

    def __init__(self, path: str) -> None:
        """Запоминает путь к базе; подключение открывается отдельно при старте приложения."""

        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Открывает соединение и создает папку для файла базы, если ее еще нет."""

        db_path = Path(self.path)
        if db_path.parent != Path("."):
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = await aiosqlite.connect(db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.execute("PRAGMA journal_mode = WAL")
        await self.connection.commit()

    async def close(self) -> None:
        """Закрывает соединение при остановке polling."""

        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    async def init_schema(self) -> None:
        """Создает таблицы, если база запускается впервые."""

        db = self._db()
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                current_step INTEGER NOT NULL DEFAULT 0,
                total_steps INTEGER NOT NULL,
                profile_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id)
            );

            CREATE TABLE IF NOT EXISTS quiz_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                step INTEGER NOT NULL,
                question_code TEXT NOT NULL,
                question_title TEXT NOT NULL,
                profile_key TEXT NOT NULL,
                answer_code TEXT NOT NULL,
                answer_label TEXT NOT NULL,
                answer_value TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES quiz_sessions (id)
            );

            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                session_id INTEGER,
                event_name TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES quiz_sessions (id)
            );

            CREATE TABLE IF NOT EXISTS course_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                quiz_session_id INTEGER,
                status TEXT NOT NULL,
                current_module INTEGER NOT NULL DEFAULT 0,
                total_modules INTEGER NOT NULL,
                profile_json TEXT NOT NULL DEFAULT '{}',
                route_json TEXT NOT NULL DEFAULT '[]',
                certificate_code TEXT,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id),
                FOREIGN KEY (quiz_session_id) REFERENCES quiz_sessions (id)
            );

            CREATE TABLE IF NOT EXISTS course_module_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_session_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                module_index INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_session_id) REFERENCES course_sessions (id)
            );

            CREATE TABLE IF NOT EXISTS user_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                file_type TEXT NOT NULL,
                telegram_file_id TEXT NOT NULL,
                telegram_file_unique_id TEXT NOT NULL,
                local_path TEXT NOT NULL,
                source TEXT NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id)
            );
            """
        )
        await db.commit()

    async def upsert_user(self, user: User) -> None:
        """Создает или обновляет Telegram-профиль пользователя."""

        db = self._db()
        await db.execute(
            """
            INSERT INTO users (
                telegram_user_id,
                username,
                first_name,
                last_name,
                language_code
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                user.language_code,
            ),
        )
        await db.commit()

    async def create_session(self, user_id: int, total_steps: int, profile: dict[str, str]) -> int:
        """Создает новую сессию прохождения теста и возвращает ее id."""

        db = self._db()
        cursor = await db.execute(
            """
            INSERT INTO quiz_sessions (
                telegram_user_id,
                status,
                current_step,
                total_steps,
                profile_json
            )
            VALUES (?, 'started', 0, ?, ?)
            """,
            (user_id, total_steps, self._json(profile)),
        )
        await db.commit()
        return int(cursor.lastrowid)

    async def update_session(self, session_id: int, current_step: int, profile: dict[str, str]) -> None:
        """Обновляет прогресс и актуальный профиль внутри незавершенной сессии."""

        db = self._db()
        await db.execute(
            """
            UPDATE quiz_sessions
            SET current_step = ?,
                profile_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_step, self._json(profile), session_id),
        )
        await db.commit()

    async def finish_session(self, session_id: int, profile: dict[str, str], result: dict[str, Any]) -> None:
        """Помечает сессию завершенной и сохраняет финальный герой-роадмап."""

        db = self._db()
        await db.execute(
            """
            UPDATE quiz_sessions
            SET status = 'finished',
                current_step = total_steps,
                profile_json = ?,
                result_json = ?,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (self._json(profile), self._json(result), session_id),
        )
        await db.commit()

    async def abandon_session(self, session_id: int | None) -> None:
        """Закрывает старую сессию как прерванную, если пользователь начал заново."""

        if session_id is None:
            return

        db = self._db()
        await db.execute(
            """
            UPDATE quiz_sessions
            SET status = 'abandoned',
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'started'
            """,
            (session_id,),
        )
        await db.commit()

    async def save_answer(
        self,
        *,
        session_id: int,
        user_id: int,
        step: int,
        question_code: str,
        question_title: str,
        profile_key: str,
        answer_code: str,
        answer_label: str,
        answer_value: str,
        source: str,
    ) -> None:
        """Сохраняет один ответ пользователя в нормализованную таблицу."""

        db = self._db()
        await db.execute(
            """
            INSERT INTO quiz_answers (
                session_id,
                telegram_user_id,
                step,
                question_code,
                question_title,
                profile_key,
                answer_code,
                answer_label,
                answer_value,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                step,
                question_code,
                question_title,
                profile_key,
                answer_code,
                answer_label,
                answer_value,
                source,
            ),
        )
        await db.commit()

    async def save_event(
        self,
        *,
        user_id: int,
        event_name: str,
        payload: dict[str, Any] | None = None,
        session_id: int | None = None,
    ) -> None:
        """Сохраняет аналитическое событие в SQLite."""

        db = self._db()
        await db.execute(
            """
            INSERT INTO analytics_events (
                telegram_user_id,
                session_id,
                event_name,
                payload_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, session_id, event_name, self._json(payload or {})),
        )
        await db.commit()

    async def get_top_interest_answers(self, goal_code: str, limit: int = 10) -> list[dict[str, Any]]:
        """Считает TOP навыков/специальностей по фактическим ответам пользователей."""

        db = self._db()
        cursor = await db.execute(
            """
            SELECT
                a.answer_code,
                a.answer_label,
                a.answer_value,
                a.source,
                a.created_at,
                s.profile_json
            FROM quiz_answers AS a
            JOIN quiz_sessions AS s ON s.id = a.session_id
            WHERE a.profile_key = 'interest'
            ORDER BY a.created_at DESC
            """
        )
        rows = await cursor.fetchall()

        counters: dict[str, dict[str, Any]] = {}
        for row in rows:
            profile = self._loads(row["profile_json"])
            if profile.get("goal_code") != goal_code:
                continue

            label = str(row["answer_label"]).strip()
            value = str(row["answer_value"]).strip()
            if not label or not value:
                continue

            if row["source"] == "manual" or row["answer_code"] == "custom":
                key = f"manual:{label.casefold()}"
                code = "user_" + hashlib.sha1(label.casefold().encode("utf-8")).hexdigest()[:12]
            else:
                key = f"button:{row['answer_code']}"
                code = str(row["answer_code"])

            current = counters.setdefault(
                key,
                {
                    "code": code,
                    "label": label,
                    "value": value,
                    "tone": "популярно у пользователей",
                    "count": 0,
                    "last_seen": row["created_at"],
                },
            )
            current["count"] += 1
            if row["created_at"] > current["last_seen"]:
                current["last_seen"] = row["created_at"]

        ranked = sorted(counters.values(), key=lambda item: (item["count"], item["last_seen"]), reverse=True)
        return ranked[:limit]

    async def get_session_snapshot(self, session_id: int) -> dict[str, Any] | None:
        """Возвращает сохраненный профиль и результат по id онбординг-сессии."""

        db = self._db()
        cursor = await db.execute(
            """
            SELECT
                s.id,
                s.telegram_user_id,
                s.status,
                s.current_step,
                s.total_steps,
                s.profile_json,
                s.result_json,
                s.started_at,
                s.finished_at,
                u.username,
                u.first_name,
                u.last_name
            FROM quiz_sessions AS s
            LEFT JOIN users AS u ON u.telegram_user_id = s.telegram_user_id
            WHERE s.id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return {
            "id": row["id"],
            "telegram_user_id": row["telegram_user_id"],
            "status": row["status"],
            "current_step": row["current_step"],
            "total_steps": row["total_steps"],
            "profile": self._loads(row["profile_json"]),
            "result": self._loads(row["result_json"] or "{}"),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "user": {
                "username": row["username"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
            },
        }

    async def get_session_answers(self, session_id: int) -> list[dict[str, Any]]:
        """Отдает ответы пользователя для истории онбординга и аналитики."""

        db = self._db()
        cursor = await db.execute(
            """
            SELECT
                step,
                question_code,
                question_title,
                profile_key,
                answer_code,
                answer_label,
                answer_value,
                source,
                created_at
            FROM quiz_answers
            WHERE session_id = ?
            ORDER BY step ASC, id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def create_course_session(
        self,
        *,
        user_id: int,
        quiz_session_id: int | None,
        profile: dict[str, str],
        route: list[dict[str, Any]],
    ) -> int:
        """Создает чатовую сессию прохождения курса."""

        db = self._db()
        cursor = await db.execute(
            """
            INSERT INTO course_sessions (
                telegram_user_id,
                quiz_session_id,
                status,
                current_module,
                total_modules,
                profile_json,
                route_json
            )
            VALUES (?, ?, 'started', 0, ?, ?, ?)
            """,
            (user_id, quiz_session_id, len(route), self._json(profile), self._json(route)),
        )
        await db.commit()
        return int(cursor.lastrowid)

    async def get_course_session(self, course_id: int) -> dict[str, Any] | None:
        """Возвращает сохраненный курс вместе с прогрессом."""

        db = self._db()
        cursor = await db.execute(
            """
            SELECT
                id,
                telegram_user_id,
                quiz_session_id,
                status,
                current_module,
                total_modules,
                profile_json,
                route_json,
                certificate_code,
                started_at,
                finished_at
            FROM course_sessions
            WHERE id = ?
            """,
            (course_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return {
            "id": row["id"],
            "telegram_user_id": row["telegram_user_id"],
            "quiz_session_id": row["quiz_session_id"],
            "status": row["status"],
            "current_module": row["current_module"],
            "total_modules": row["total_modules"],
            "profile": self._loads(row["profile_json"]),
            "route": self._loads_value(row["route_json"], []),
            "certificate_code": row["certificate_code"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    async def update_course_progress(self, course_id: int, current_module: int) -> None:
        """Сохраняет индекс текущего модуля курса."""

        db = self._db()
        await db.execute(
            """
            UPDATE course_sessions
            SET current_module = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_module, course_id),
        )
        await db.commit()

    async def complete_course_session(self, course_id: int, certificate_code: str) -> None:
        """Помечает курс завершенным и сохраняет код сертификата."""

        db = self._db()
        await db.execute(
            """
            UPDATE course_sessions
            SET status = 'completed',
                current_module = total_modules,
                certificate_code = ?,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (certificate_code, course_id),
        )
        await db.commit()

    async def save_course_event(
        self,
        *,
        course_id: int,
        user_id: int,
        module_index: int,
        event_name: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Фиксирует события прохождения курса и обратную связь по модулю."""

        db = self._db()
        await db.execute(
            """
            INSERT INTO course_module_events (
                course_session_id,
                telegram_user_id,
                module_index,
                event_name,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_id, user_id, module_index, event_name, self._json(payload or {})),
        )
        await db.commit()

    async def save_certificate(
        self,
        *,
        user_id: int,
        title: str,
        file_type: str,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        local_path: str,
        source: str,
    ) -> int:
        """Сохраняет метаданные загруженного пользователем сертификата."""

        db = self._db()
        cursor = await db.execute(
            """
            INSERT INTO user_certificates (
                telegram_user_id,
                title,
                file_type,
                telegram_file_id,
                telegram_file_unique_id,
                local_path,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, file_type, telegram_file_id, telegram_file_unique_id, local_path, source),
        )
        await db.commit()
        return int(cursor.lastrowid)

    async def list_user_certificates(self, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
        """Показывает последние сертификаты, загруженные пользователем."""

        db = self._db()
        cursor = await db.execute(
            """
            SELECT
                id,
                title,
                file_type,
                telegram_file_id,
                telegram_file_unique_id,
                local_path,
                source,
                uploaded_at
            FROM user_certificates
            WHERE telegram_user_id = ?
            ORDER BY uploaded_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    def _db(self) -> aiosqlite.Connection:
        """Возвращает активное соединение или явно сообщает о неправильном старте."""

        if self.connection is None:
            raise RuntimeError("База данных не подключена.")
        return self.connection

    @staticmethod
    def _json(value: Any) -> str:
        """Сериализует словари и списки так, чтобы русские тексты оставались читаемыми."""

        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _loads(value: str) -> dict[str, Any]:
        """Безопасно читает JSON-профиль из SQLite."""

        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _loads_value(value: str, fallback: Any) -> Any:
        """Безопасно читает произвольный JSON из SQLite."""

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
