from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bot.infrastructure.config import Settings
from bot.infrastructure.miniapp_data import MiniAppDataRepository


class MiniAppRequestHandler(SimpleHTTPRequestHandler):
    repository: MiniAppDataRepository

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/roadmap":
            try:
                params = parse_qs(parsed.query)
                user_id = as_int(first(params.get("telegram_user_id")))
                self.send_json(self.repository.get_roadmap(user_id))
            except Exception as error:
                self.send_json({"ok": False, "error": str(error)}, status=500)
            return
        if parsed.path in {"/api/admin/summary", "/api/admin/routes", "/api/admin/onboarding-payloads"}:
            try:
                self.send_json(self.repository.admin_summary())
            except Exception as error:
                self.send_json({"ok": False, "error": str(error)}, status=500)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/progress/mark", "/api/feedback", "/api/certificates/upload", "/api/roadmap/rebuild"}:
            self.send_error(404)
            return

        payload = self.read_json()
        if parsed.path == "/api/roadmap/rebuild":
            course_id = as_int(payload.get("courseId"))
            user_id = as_int(payload.get("telegramUserId"))
            reason = str(payload.get("reason") or "manual")
            result = self.repository.rebuild_roadmap(course_id, user_id, reason)
            self.send_json(result, status=200 if result.get("ok") else 404)
            return

        if parsed.path == "/api/certificates/upload":
            try:
                result = self.repository.upload_certificate(payload, as_int(payload.get("telegramUserId")))
            except ValueError as error:
                self.send_json({"ok": False, "error": str(error)}, status=400)
                return
            except Exception as error:
                self.send_json({"ok": False, "error": str(error)}, status=500)
                return
            self.send_json(result, status=201 if result.get("ok") else 400)
            return

        course_id = as_int(payload.get("courseId"))
        module_index = as_int(payload.get("moduleIndex"))
        user_id = as_int(payload.get("telegramUserId"))
        if course_id is None or module_index is None:
            self.send_json({"ok": False, "error": "courseId and moduleIndex are required"}, status=400)
            return

        try:
            if parsed.path == "/api/progress/mark":
                result = self.repository.mark_module(course_id, module_index, user_id)
            else:
                result = self.repository.save_feedback(
                    course_id,
                    module_index,
                    str(payload.get("feedback") or "useful"),
                    user_id,
                )
        except Exception as error:
            self.send_json({"ok": False, "error": str(error)}, status=500)
            return
        self.send_json(result, status=200 if result.get("ok") else 404)

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        translated = super().translate_path(parsed.path)
        if Path(translated).exists():
            return translated

        # Telegram WebView may reopen nested paths. Keep React SPA alive.
        index_path = Path(os.getcwd()) / "index.html"
        return str(index_path)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    settings = Settings()
    repository = MiniAppDataRepository(settings.database_path)
    port = int(os.environ.get("MINIAPP_PORT", "8080"))
    static_dir = os.environ.get("MINIAPP_STATIC_DIR", "/app/miniapp")
    os.chdir(static_dir)
    MiniAppRequestHandler.repository = repository
    server = ThreadingHTTPServer(("0.0.0.0", port), MiniAppRequestHandler)
    print(f"Mini App server started on :{port}; db={settings.database_path}; static={static_dir}")
    server.serve_forever()


def first(values: list[str] | None) -> str | None:
    return values[0] if values else None


def as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    run()
