import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError


class TelegramApi:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": json.dumps(["message", "callback_query"])}
        if offset is not None:
            params["offset"] = offset
        return self._request("getUpdates", params).get("result", [])

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        self._request("sendMessage", payload)

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        self._request("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

    def _request(self, method: str, payload: dict) -> dict:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.base_url}/{method}", data=data)
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8")
            raise RuntimeError(f"Telegram API {method} failed: HTTP {error.code}: {body}") from error
        result = json.loads(body)
        if not result.get("ok"):
            raise RuntimeError(result)
        return result
