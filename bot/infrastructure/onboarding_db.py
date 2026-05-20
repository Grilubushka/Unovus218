from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


class OnboardingDatabase:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        if self.path.parent != Path("."):
            self.path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.commit()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def init_schema(self) -> None:
        db = self._db()
        db.executescript(
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
        db.commit()

    def upsert_user(self, user: dict[str, Any], fallback_user_id: int) -> None:
        db = self._db()
        db.execute(
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
                int(user.get("id") or fallback_user_id),
                user.get("username"),
                user.get("first_name"),
                user.get("last_name"),
                user.get("language_code"),
            ),
        )
        db.commit()

    def create_session(self, user_id: int, total_steps: int, profile: dict[str, str]) -> int:
        cursor = self._db().execute(
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
        self._db().commit()
        return int(cursor.lastrowid)

    def update_session(self, session_id: int, current_step: int, profile: dict[str, str]) -> None:
        self._db().execute(
            """
            UPDATE quiz_sessions
            SET current_step = ?,
                profile_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_step, self._json(profile), session_id),
        )
        self._db().commit()

    def finish_session(self, session_id: int, profile: dict[str, str], result: dict[str, Any]) -> None:
        self._db().execute(
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
        self._db().commit()

    def abandon_session(self, session_id: int | None) -> None:
        if session_id is None:
            return

        self._db().execute(
            """
            UPDATE quiz_sessions
            SET status = 'abandoned',
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'started'
            """,
            (session_id,),
        )
        self._db().commit()

    def save_answer(
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
        self._db().execute(
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
        self._db().commit()

    def save_event(
        self,
        *,
        user_id: int,
        event_name: str,
        payload: dict[str, Any] | None = None,
        session_id: int | None = None,
    ) -> None:
        self._db().execute(
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
        self._db().commit()

    def get_top_interest_answers(self, goal_code: str, limit: int = 10) -> list[dict[str, Any]]:
        cursor = self._db().execute(
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
        rows = cursor.fetchall()

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

    def get_session_snapshot(self, session_id: int) -> dict[str, Any] | None:
        cursor = self._db().execute(
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
                u.last_name,
                u.language_code
            FROM quiz_sessions AS s
            LEFT JOIN users AS u ON u.telegram_user_id = s.telegram_user_id
            WHERE s.id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
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
                "language_code": row["language_code"],
            },
        }

    def get_session_answers(self, session_id: int) -> list[dict[str, Any]]:
        cursor = self._db().execute(
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
        return [dict(row) for row in cursor.fetchall()]

    def create_course_session(
        self,
        *,
        user_id: int,
        quiz_session_id: int | None,
        profile: dict[str, str],
        route: list[dict[str, Any]],
    ) -> int:
        cursor = self._db().execute(
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
            VALUES (?, ?, 'active', 0, ?, ?, ?)
            """,
            (user_id, quiz_session_id, len(route), self._json(profile), self._json(route)),
        )
        self._db().commit()
        return int(cursor.lastrowid)

    def list_active_routes(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._db().execute(
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
                started_at,
                updated_at
            FROM course_sessions
            WHERE telegram_user_id = ?
              AND status IN ('active', 'started', 'completed')
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

        return [self._course_row(row) for row in rows]

    def get_course_session(self, course_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        query = """
            SELECT
                id,
                telegram_user_id,
                quiz_session_id,
                status,
                current_module,
                total_modules,
                profile_json,
                route_json,
                started_at,
                updated_at
            FROM course_sessions
            WHERE id = ?
        """
        params: tuple[Any, ...] = (course_id,)
        if user_id is not None:
            query += " AND telegram_user_id = ?"
            params = (course_id, user_id)

        row = self._db().execute(query, params).fetchone()
        return self._course_row(row) if row is not None else None

    def _db(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("База данных онбординга не подключена.")
        return self.connection

    def _course_row(self, row: sqlite3.Row) -> dict[str, Any]:
        route = self._loads_value(row["route_json"], [])
        return {
            "id": row["id"],
            "telegram_user_id": row["telegram_user_id"],
            "quiz_session_id": row["quiz_session_id"],
            "status": row["status"],
            "current_module": row["current_module"],
            "total_modules": row["total_modules"],
            "profile": self._loads(row["profile_json"]),
            "route": route if isinstance(route, list) else [],
            "started_at": row["started_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _loads(value: str) -> dict[str, Any]:
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    @staticmethod
    def _loads_value(value: str, fallback: Any) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
