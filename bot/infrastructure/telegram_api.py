import json
import socket
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from urllib.error import HTTPError, URLError


class TelegramApi:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": json.dumps(["message", "callback_query"])}
        if offset is not None:
            params["offset"] = offset
        return self._request("getUpdates", params, timeout=timeout + 20, retries=1).get("result", [])

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        return self._request("sendMessage", payload).get("result", {})

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        result = self._request("editMessageText", payload).get("result", {})
        return result if isinstance(result, dict) else {}

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        try:
            self._request("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text}, timeout=8, retries=1)
        except RuntimeError as error:
            if "query is too old" in str(error).lower() or "query id is invalid" in str(error).lower():
                return
            raise

    def _request(self, method: str, payload: dict, *, timeout: int = 25, retries: int = 3) -> dict:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}/{method}", data=data)
        body = ""
        last_error: BaseException | None = None
        for attempt in range(retries):
            try:
                with force_ipv4_dns(), urllib.request.urlopen(request, timeout=timeout) as response:
                    body = response.read().decode("utf-8")
                break
            except HTTPError as error:
                body = error.read().decode("utf-8")
                raise RuntimeError(f"Telegram API {method} failed: HTTP {error.code}: {body}") from error
            except (TimeoutError, URLError, OSError) as error:
                last_error = error
                if attempt == retries - 1:
                    raise RuntimeError(f"Telegram API {method} failed after retries: {error}") from error
                time.sleep(1.5 * (attempt + 1))
        if not body:
            raise RuntimeError(f"Telegram API {method} failed: {last_error}")
        result = json.loads(body)
        if not result.get("ok"):
            raise RuntimeError(result)
        return result


@contextmanager
def force_ipv4_dns():
    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = getaddrinfo_ipv4
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo
