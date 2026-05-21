from __future__ import annotations

import base64
import binascii
from datetime import datetime
import json
import mimetypes
import sqlite3
from pathlib import Path
from typing import Any


class MiniAppDataRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = str(Path(database_path).resolve())

    def get_roadmap(self, telegram_user_id: int | None = None) -> dict[str, Any]:
        if telegram_user_id is None:
            return self._empty_roadmap_response("telegram_user_id_required", has_completed_onboarding=False)

        with self._connect() as db:
            if not self._has_course_schema(db):
                return self._empty_roadmap_response("course_schema_missing", has_completed_onboarding=False)

            has_completed_onboarding = self._has_completed_onboarding(db, telegram_user_id)
            if not has_completed_onboarding:
                return self._empty_roadmap_response(
                    "onboarding_required",
                    has_completed_onboarding=False,
                    user=self._user(db, telegram_user_id),
                )

            course = self._latest_course(db, telegram_user_id)
            if course is None:
                return self._empty_roadmap_response(
                    "route_missing",
                    has_completed_onboarding=True,
                    user=self._user(db, telegram_user_id),
                )

            profile = self._loads(course["profile_json"], {})
            route = self._loads(course["route_json"], [])
            certificates = self._certificates(db, int(course["telegram_user_id"]))
            events = self._module_events(db, int(course["id"]))
            answers = self._answers(db, int(course["quiz_session_id"] or 0))
            user = self._user(db, int(course["telegram_user_id"]))

            modules = [self._module(item, index, course, events) for index, item in enumerate(route)]
            total_modules = max(int(course["total_modules"] or len(modules) or 1), 1)
            current_module = int(course["current_module"] or 0)
            progress = 100 if course["status"] == "completed" else round(current_module / total_modules * 100)

            return {
                "source": "database",
                "hasData": True,
                "hasCompletedOnboarding": True,
                "telegramUserId": int(course["telegram_user_id"]),
                "id": f"course-{course['id']}",
                "title": self._title(profile, route),
                "domainTitle": profile.get("interest_tone") or "Персональный трек",
                "explanation": self._explanation(profile, course),
                "progress": progress,
                "status": course["status"],
                "profile": self._profile(profile),
                "modules": modules,
                "stats": self._stats(modules, course, certificates, answers),
                "user": user,
                "certificates": certificates,
                "events": events,
                "startedAt": course["started_at"],
                "updatedAt": course["updated_at"],
            }

    def mark_module(self, course_id: int, module_index: int, telegram_user_id: int | None = None) -> dict[str, Any]:
        if telegram_user_id is None:
            return {"ok": False, "error": "telegram_user_id_required"}

        with self._connect() as db:
            if not self._has_course_schema(db):
                return {"ok": False, "error": "course_schema_missing"}

            course = self._course_by_id(db, course_id, telegram_user_id)
            if course is None:
                return {"ok": False, "error": "course_not_found"}

            user_id = int(telegram_user_id)
            next_module = max(int(course["current_module"] or 0), module_index + 1)
            status = "completed" if next_module >= int(course["total_modules"] or 0) else course["status"]
            db.execute(
                """
                UPDATE course_sessions
                SET current_module = ?,
                    status = ?,
                    finished_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE finished_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_module, status, status, course_id),
            )
            self._save_module_event(db, course_id, user_id, module_index, "module_completed", {"source": "miniapp"})
            db.commit()
        return {"ok": True}

    def save_feedback(
        self,
        course_id: int,
        module_index: int,
        feedback: str,
        telegram_user_id: int | None = None,
    ) -> dict[str, Any]:
        if telegram_user_id is None:
            return {"ok": False, "error": "telegram_user_id_required"}

        with self._connect() as db:
            if not self._has_course_schema(db):
                return {"ok": False, "error": "course_schema_missing"}

            course = self._course_by_id(db, course_id, telegram_user_id)
            if course is None:
                return {"ok": False, "error": "course_not_found"}
            user_id = int(telegram_user_id)
            self._save_module_event(db, course_id, user_id, module_index, "module_feedback", {"feedback": feedback})
            db.commit()
        return {"ok": True}

    def upload_certificate(self, payload: dict[str, Any], telegram_user_id: int | None = None) -> dict[str, Any]:
        if telegram_user_id is None:
            raise ValueError("telegramUserId is required")

        with self._connect() as db:
            if not self._has_certificate_schema(db):
                return {"ok": False, "error": "certificate_schema_missing"}

            user_id = int(telegram_user_id)
            title = str(payload.get("title") or payload.get("fileName") or "Сертификат").strip()[:160]
            file_type = str(payload.get("fileType") or "application/octet-stream").strip()[:120]
            file_name = self._safe_file_name(str(payload.get("fileName") or title), file_type)
            file_bytes = self._decode_data_url(str(payload.get("dataUrl") or ""))
            if len(file_bytes) > 12 * 1024 * 1024:
                return {"ok": False, "error": "file_too_large"}

            target_dir = Path(self.database_path).parent / "certificates" / str(user_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            local_path = target_dir / f"{timestamp}_{file_name}"
            local_path.write_bytes(file_bytes)

            unique_id = f"miniapp-{user_id}-{timestamp}-{abs(hash(local_path.name))}"
            cursor = db.execute(
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
                (user_id, title or "Сертификат", file_type, unique_id, unique_id, str(local_path), "miniapp"),
            )
            db.commit()
            certificate = self._certificate_by_id(db, int(cursor.lastrowid))
        return {"ok": True, "certificate": certificate}

    def _connect(self) -> sqlite3.Connection:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _has_course_schema(db: sqlite3.Connection) -> bool:
        row = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'course_sessions'
            """
        ).fetchone()
        return row is not None

    @staticmethod
    def _has_certificate_schema(db: sqlite3.Connection) -> bool:
        row = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'user_certificates'
            """
        ).fetchone()
        return row is not None

    @staticmethod
    def _has_quiz_schema(db: sqlite3.Connection) -> bool:
        row = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'quiz_sessions'
            """
        ).fetchone()
        return row is not None

    @staticmethod
    def _has_completed_onboarding(db: sqlite3.Connection, telegram_user_id: int) -> bool:
        if MiniAppDataRepository._has_quiz_schema(db):
            row = db.execute(
                """
                SELECT 1
                FROM quiz_sessions
                WHERE telegram_user_id = ?
                  AND status = 'finished'
                LIMIT 1
                """,
                (telegram_user_id,),
            ).fetchone()
            if row is not None:
                return True

        row = db.execute(
            """
            SELECT 1
            FROM course_sessions
            WHERE telegram_user_id = ?
            LIMIT 1
            """,
            (telegram_user_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _latest_course(db: sqlite3.Connection, telegram_user_id: int) -> sqlite3.Row | None:
        return db.execute(
            """
            SELECT * FROM course_sessions
            WHERE telegram_user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (telegram_user_id,),
        ).fetchone()

    @staticmethod
    def _course_by_id(db: sqlite3.Connection, course_id: int, telegram_user_id: int | None = None) -> sqlite3.Row | None:
        if telegram_user_id is None:
            return db.execute("SELECT * FROM course_sessions WHERE id = ?", (course_id,)).fetchone()
        return db.execute(
            "SELECT * FROM course_sessions WHERE id = ? AND telegram_user_id = ?",
            (course_id, telegram_user_id),
        ).fetchone()

    @staticmethod
    def _user(db: sqlite3.Connection, telegram_user_id: int) -> dict[str, Any]:
        row = db.execute("SELECT * FROM users WHERE telegram_user_id = ?", (telegram_user_id,)).fetchone()
        return dict(row) if row is not None else {"telegram_user_id": telegram_user_id}

    @staticmethod
    def _empty_roadmap_response(
        reason: str,
        *,
        has_completed_onboarding: bool,
        user: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": "database",
            "hasData": False,
            "hasCompletedOnboarding": has_completed_onboarding,
            "reason": reason,
        }
        if user is not None:
            payload["user"] = user
        return payload

    @staticmethod
    def _certificates(db: sqlite3.Connection, telegram_user_id: int) -> list[dict[str, Any]]:
        rows = db.execute(
            """
            SELECT id, title, file_type, local_path, source, uploaded_at
            FROM user_certificates
            WHERE telegram_user_id = ?
            ORDER BY uploaded_at DESC
            """,
            (telegram_user_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _certificate_by_id(db: sqlite3.Connection, certificate_id: int) -> dict[str, Any]:
        row = db.execute(
            """
            SELECT id, title, file_type, local_path, source, uploaded_at
            FROM user_certificates
            WHERE id = ?
            """,
            (certificate_id,),
        ).fetchone()
        return dict(row) if row is not None else {}

    @staticmethod
    def _answers(db: sqlite3.Connection, session_id: int) -> list[dict[str, Any]]:
        if not session_id:
            return []
        rows = db.execute(
            """
            SELECT question_title, answer_label, answer_value, created_at
            FROM quiz_answers
            WHERE session_id = ?
            ORDER BY step ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _module_events(db: sqlite3.Connection, course_session_id: int) -> list[dict[str, Any]]:
        rows = db.execute(
            """
            SELECT module_index, event_name, payload_json, created_at
            FROM course_module_events
            WHERE course_session_id = ?
            ORDER BY id DESC
            """,
            (course_session_id,),
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["payload"] = MiniAppDataRepository._loads(item.pop("payload_json"), {})
            events.append(item)
        return events

    @staticmethod
    def _module(item: dict[str, Any], index: int, course: sqlite3.Row, events: list[dict[str, Any]]) -> dict[str, Any]:
        current_module = int(course["current_module"] or 0)
        if course["status"] == "completed" or index < current_module:
            progress = 100
            status = "completed"
        elif index == current_module:
            progress = 35
            status = "current"
        else:
            progress = 0
            status = "locked"

        feedback = [
            event["payload"].get("feedback")
            for event in events
            if int(event["module_index"]) == index and event["event_name"] == "module_feedback"
        ]

        topic = {
            "id": f"course-{course['id']}-topic-{index}",
            "title": item.get("title") or f"Модуль {index + 1}",
            "progress": progress,
            "status": status,
            "description": item.get("description") or item.get("outcome") or "",
            "skills": MiniAppDataRepository._skills(item),
            "competency": item.get("outcome") or "После модуля появится понятный практический результат.",
            "practice": item.get("practice"),
            "checkpoint": item.get("checkpoint"),
            "moduleIndex": index,
            "courseId": int(course["id"]),
            "feedback": feedback,
            "materials": [
                MiniAppDataRepository._material(material, material_index)
                for material_index, material in enumerate(item.get("materials") or [])
            ],
        }

        return {
            "id": f"course-{course['id']}-module-{index}",
            "title": item.get("title") or f"Модуль {index + 1}",
            "goal": item.get("outcome") or item.get("description") or "",
            "duration": item.get("duration"),
            "progress": progress,
            "status": status,
            "sections": [
                {
                    "id": f"course-{course['id']}-section-{index}",
                    "title": item.get("duration") or "Материалы и практика",
                    "topics": [topic],
                }
            ],
        }

    @staticmethod
    def _material(material: dict[str, Any], index: int) -> dict[str, Any]:
        kind = str(material.get("kind") or "Материал")
        return {
            "id": f"material-{index}-{abs(hash(material.get('title', '')))}",
            "format": MiniAppDataRepository._format(kind),
            "kind": kind,
            "title": material.get("title") or kind,
            "source": material.get("source") or "Открытый русскоязычный источник",
            "duration": material.get("duration") or "",
            "interaction": material.get("interaction") or "",
            "isFree": True,
            "language": "ru",
        }

    @staticmethod
    def _format(kind: str) -> str:
        lowered = kind.lower()
        if "видео" in lowered or "лекц" in lowered:
            return "video"
        if "стат" in lowered or "консп" in lowered:
            return "article"
        if "тест" in lowered or "проверк" in lowered:
            return "quiz"
        return "practice"

    @staticmethod
    def _profile(profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "goal": profile.get("goal") or "Персональная цель",
            "direction": profile.get("interest") or "Персональный трек",
            "age": profile.get("age_code") or "",
            "ageLabel": profile.get("age") or "возраст не указан",
            "experience": profile.get("level_code") or "",
            "experienceLabel": profile.get("level") or "уровень не указан",
            "weeklyTime": profile.get("time_code") or "",
            "weeklyTimeLabel": profile.get("time") or "темп не указан",
            "formats": ["материалы", "практика"],
            "formatsLabel": profile.get("constraints_tone") or "персональная подача",
            "routeMode": profile.get("goal_tone") or "персональный режим",
            "focus": profile.get("focus") or "",
            "constraints": profile.get("constraints") or "",
        }

    @staticmethod
    def _stats(
        modules: list[dict[str, Any]],
        course: sqlite3.Row,
        certificates: list[dict[str, Any]],
        answers: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        completed = sum(1 for module in modules if module["progress"] == 100)
        return [
            {"value": str(len(modules)), "label": "модулей в персональном маршруте", "tone": "blue"},
            {"value": f"{completed}/{len(modules)}", "label": "модулей завершено по базе", "tone": "green"},
            {"value": str(len(answers)), "label": "ответов онбординга учтено", "tone": "pink"},
            {"value": str(len(certificates)), "label": "сертификатов загружено", "tone": "plain"},
        ]

    @staticmethod
    def _title(profile: dict[str, Any], route: list[dict[str, Any]]) -> str:
        if profile.get("interest"):
            return str(profile["interest"]).replace("интересуется ", "").replace("хочет ", "").capitalize()
        if route:
            return route[0].get("title", "Персональный маршрут")
        return "Персональный маршрут"

    @staticmethod
    def _explanation(profile: dict[str, Any], course: sqlite3.Row) -> str:
        parts = [
            profile.get("goal"),
            profile.get("interest"),
            profile.get("time"),
        ]
        text = ". ".join(part for part in parts if part)
        return text or f"Маршрут собран из базы по сессии #{course['id']}."

    @staticmethod
    def _skills(item: dict[str, Any]) -> list[str]:
        skills = [item.get("duration"), item.get("outcome"), item.get("practice")]
        return [str(skill) for skill in skills if skill][:4] or ["практика", "самопроверка"]

    @staticmethod
    def _save_module_event(
        db: sqlite3.Connection,
        course_id: int,
        user_id: int,
        module_index: int,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        db.execute(
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
            (course_id, user_id, module_index, event_name, json.dumps(payload, ensure_ascii=False)),
        )

    @staticmethod
    def _decode_data_url(data_url: str) -> bytes:
        if not data_url:
            raise ValueError("dataUrl is required")
        encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
        try:
            return base64.b64decode(encoded, validate=True)
        except binascii.Error as error:
            raise ValueError("invalid dataUrl") from error

    @staticmethod
    def _safe_file_name(file_name: str, file_type: str) -> str:
        raw_name = Path(file_name).name.strip() or "certificate"
        allowed = []
        for char in raw_name:
            if char.isalnum() or char in {".", "-", "_"}:
                allowed.append(char)
            elif char.isspace():
                allowed.append("_")
        safe_name = "".join(allowed).strip("._") or "certificate"
        if "." not in safe_name:
            safe_name += mimetypes.guess_extension(file_type) or ".bin"
        return safe_name[:120]

    @staticmethod
    def _loads(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return fallback
        return loaded
