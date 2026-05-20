from __future__ import annotations

import json
import urllib.request
from urllib.error import HTTPError, URLError


class LlmAgentClient:
    """Small OpenAI-compatible Chat Completions client for the onboarding copy agent."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        model: str,
        timeout: float,
        max_tokens: int = 0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.token}",
                "content-type": "application/json",
            },
        )
        try:
            timeout = self.timeout if self.timeout > 0 else None
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM agent failed: HTTP {error.code}: {body}") from error
        except URLError as error:
            raise RuntimeError(f"LLM agent failed: {error}") from error

        result = json.loads(body)
        choices = result.get("choices") or []
        if not choices:
            raise RuntimeError("LLM agent returned no choices.")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM agent returned empty content.")
        return content
