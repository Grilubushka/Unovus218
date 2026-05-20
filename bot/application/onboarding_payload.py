from __future__ import annotations

import json
from typing import Any, Mapping

from bot.application.profile_flow import get_result, recommended_specialties


PROFILE_KEYS = ("goal", "interest", "age", "focus", "level", "time", "constraints")
SCHEMA_VERSION = "admin.onboarding.v1"


def build_admin_onboarding_payload(
    *,
    telegram_user_id: int,
    chat_id: int,
    quiz_session_id: int | None,
    course_session_id: int | None,
    profile: Mapping[str, Any],
    answers: list[Mapping[str, Any]],
    route: list[Mapping[str, Any]],
    user: Mapping[str, Any] | None = None,
    submitted_at: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "source": "telegram_bot",
        "status": "finished",
        "telegramUserId": telegram_user_id,
        "chatId": chat_id,
        "quizSessionId": quiz_session_id,
        "courseSessionId": course_session_id,
        "profile": normalize_profile(profile),
        "rawProfile": normalize_raw_profile(profile),
        "answers": [normalize_answer(answer) for answer in answers],
        "result": normalize_result(profile),
        "route": [dict(item) for item in route],
    }

    user_payload = normalize_user(user or {})
    if user_payload:
        payload["user"] = user_payload
    if submitted_at:
        payload["submittedAt"] = submitted_at

    return payload


def build_admin_onboarding_json(payload: Mapping[str, Any], *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def normalize_profile(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for key in PROFILE_KEYS:
        item = normalize_profile_item(profile, key)
        if item:
            normalized[key] = item
    return normalized


def normalize_profile_item(profile: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = clean_string(profile.get(key))
    code = clean_string(profile.get(f"{key}_code"))
    tone = clean_string(profile.get(f"{key}_tone"))

    item = drop_empty(
        {
            "value": value,
            "code": code,
            "tone": tone,
            "codes": split_codes(code),
        }
    )
    return item


def normalize_answer(answer: Mapping[str, Any]) -> dict[str, Any]:
    answer_code = clean_string(answer.get("answer_code"))
    return drop_empty(
        {
            "step": as_int(answer.get("step")),
            "questionCode": clean_string(answer.get("question_code")),
            "questionTitle": clean_string(answer.get("question_title")),
            "profileKey": clean_string(answer.get("profile_key")),
            "answer": drop_empty(
                {
                    "code": answer_code,
                    "codes": split_codes(answer_code),
                    "label": clean_string(answer.get("answer_label")),
                    "value": clean_string(answer.get("answer_value")),
                }
            ),
            "source": clean_string(answer.get("source")),
            "createdAt": clean_string(answer.get("created_at")),
        }
    )


def normalize_result(profile: Mapping[str, Any]) -> dict[str, Any]:
    string_profile = {str(key): str(value) for key, value in profile.items() if value is not None}
    result = dict(get_result(string_profile))
    if string_profile.get("goal_code") == "explore":
        result["recommendedSpecialties"] = recommended_specialties(string_profile)
    return result


def normalize_raw_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): profile[key] for key in sorted(profile.keys())}


def normalize_user(user: Mapping[str, Any]) -> dict[str, Any]:
    return drop_empty(
        {
            "username": clean_string(user.get("username")),
            "firstName": clean_string(user.get("first_name")),
            "lastName": clean_string(user.get("last_name")),
            "languageCode": clean_string(user.get("language_code")),
        }
    )


def split_codes(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != [] and value != {}
    }
