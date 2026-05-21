# learning/services/llm.py

import json
import os
import re


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def extract_json_from_text(text: str):
    """
    Пытается распарсить:
    1. чистый JSON;
    2. JSON внутри ```json ... ```;
    3. первый JSON-объект {...} внутри текста.
    """
    if not text:
        raise LLMResponseError("LLM вернула пустой ответ.")

    cleaned = text.strip()

    # 1. Чистый JSON
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced code block with object or array
    fence_match = re.search(
        r"```(?:json)?\s*([\[{].*?[\]}])\s*```",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Первый JSON-объект или массив в тексте
    object_start = cleaned.find("{")
    array_start = cleaned.find("[")
    starts = [index for index in (object_start, array_start) if index != -1]
    if starts:
        start = min(starts)
        end_char = "}" if cleaned[start] == "{" else "]"
        end = cleaned.rfind(end_char)
        if end <= start:
            end = -1
    else:
        start = end = -1
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise LLMResponseError(f"LLM вернула невалидный JSON: {cleaned[:1000]}")


class ResponsesLLMClient:
    """Small adapter around an OpenAI-compatible Responses API client."""

    def __init__(self, llm_settings):
        self.llm_settings = llm_settings

    def create(self, payload: dict, purpose="default"):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError(
                "Не установлен пакет openai. Установите зависимости из requirements.txt."
            ) from exc

        api_key_env = self.llm_settings.api_key_env_for(purpose)
        api_key = os.getenv(api_key_env, "")
        if not api_key:
            raise LLMConfigurationError(f"Не найден API key в env-переменной {api_key_env}.")

        client_kwargs = {"api_key": api_key, "timeout": self.llm_settings.request_timeout_seconds}
        api_base_url = self.llm_settings.api_base_url_for(purpose)
        provider = self.llm_settings.provider_for(purpose)

        if api_base_url:
            client_kwargs["base_url"] = api_base_url
        elif provider == self.llm_settings.Provider.YANDEX:
            client_kwargs["base_url"] = "https://llm.api.cloud.yandex.net/v1"
        if provider == self.llm_settings.Provider.YANDEX:
            project = os.getenv(self.llm_settings.folder_id_env, "")
            if project:
                client_kwargs["project"] = project

        client = OpenAI(**client_kwargs)

        if purpose == "chat" and not payload.get("tools"):
            response_format = payload.get("response_format") or {"type": "json_object"}
            return client.chat.completions.create(
                model=payload["model"],
                messages=[
                    {"role": "system", "content": "Return only valid json. Do not include markdown or prose."},
                    {"role": "user", "content": payload["input"]},
                ],
                temperature=payload.get("temperature"),
                top_p=payload.get("top_p"),
                max_tokens=payload.get("max_output_tokens"),
                response_format=response_format,
            )

        return client.responses.create(**payload)

    def create_json(self, payload: dict, purpose="default") -> dict:
        print("\n" + "=" * 80)
        print("[LLM DEBUG] PURPOSE:", purpose)
        print("[LLM DEBUG] FULL PAYLOAD:")
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("=" * 80 + "\n", flush=True)

        response = self.create(payload, purpose=purpose)

        print("\n" + "=" * 80)
        print("[LLM DEBUG] RAW RESPONSE OBJECT TYPE:")
        print(type(response))
        print("=" * 80, flush=True)

        print("\n" + "=" * 80)
        print("[LLM DEBUG] RAW RESPONSE OBJECT:")
        print(response)
        print("=" * 80, flush=True)

        if hasattr(response, "model_dump"):
            print("\n" + "=" * 80)
            print("[LLM DEBUG] RESPONSE MODEL DUMP:")
            print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2, default=str))
            print("=" * 80, flush=True)

        if hasattr(response, "dict"):
            print("\n" + "=" * 80)
            print("[LLM DEBUG] RESPONSE DICT:")
            print(json.dumps(response.dict(), ensure_ascii=False, indent=2, default=str))
            print("=" * 80, flush=True)

        self.raise_for_failed_response(response)

        try:
            text = self.extract_text(response)
        except Exception as exc:
            print("\n" + "=" * 80)
            print("[LLM DEBUG] EXTRACT TEXT ERROR:")
            print(repr(exc))
            print("=" * 80 + "\n", flush=True)
            raise

        print("\n" + "=" * 80)
        print("[LLM DEBUG] EXTRACTED TEXT:")
        print(text)
        print("=" * 80 + "\n", flush=True)

        try:
            return extract_json_from_text(text)
        except json.JSONDecodeError as exc:
            print("\n" + "=" * 80)
            print("[LLM DEBUG] JSON PARSE ERROR:")
            print(str(exc))
            print("[LLM DEBUG] INVALID TEXT:")
            print(text)
            print("=" * 80 + "\n", flush=True)

            raise LLMResponseError(f"LLM вернула невалидный JSON: {text[:1000]}") from exc

    @staticmethod
    def raise_for_failed_response(response) -> None:
        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif isinstance(response, dict):
            data = response
        else:
            status = getattr(response, "status", None)
            error = getattr(response, "error", None)
            if status == "failed" or error:
                raise LLMResponseError(ResponsesLLMClient._format_response_error(status, error))
            return

        status = data.get("status")
        error = data.get("error")
        if status == "failed" or error:
            raise LLMResponseError(ResponsesLLMClient._format_response_error(status, error))

    @staticmethod
    def _format_response_error(status, error) -> str:
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
        else:
            code = getattr(error, "code", None)
            message = getattr(error, "message", None)

        details = ": ".join(part for part in [str(code or "").strip(), str(message or "").strip()] if part)
        if details:
            return f"LLM вернула ошибку ({status or 'unknown'}): {details}"
        return f"LLM вернула ошибку ({status or 'unknown'})."
        
    @staticmethod
    def extract_text(response) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text.strip()

        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif isinstance(response, dict):
            data = response
        else:
            raise LLMResponseError("Не удалось прочитать ответ LLM.")

        chunks = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                text = content.get("text")
                if text:
                    chunks.append(text)

        if chunks:
            return "\n".join(chunks).strip()

        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if content:
                return content.strip()

        raise LLMResponseError("В ответе LLM нет текстового JSON.")
    


def normalize_llm_json_text(text: str) -> str:
    """
    Убирает Markdown-обёртки вокруг JSON:
    ```json
    {...}
    ```
    или
    ```
    {...}
    ```
    """
    if not text:
        return text

    text = text.strip()

    # Убрать fenced code block: ```json ... ``` или ``` ... ```
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        text = match.group(1).strip()

    return text
