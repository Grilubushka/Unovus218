def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": callback_data} for text, callback_data in row]
            for row in rows
        ]
    }


def question_keyboard(question: dict) -> dict | None:
    buttons = question.get("buttons")
    if not buttons:
        return None
    rows = [[(text, f"answer:{value}")] for text, value in buttons]
    return inline_keyboard(rows)


def roadmap_keyboard(miniapp_url: str) -> dict:
    rows = [
        [
            {"text": "Продолжить обучение", "callback_data": "roadmap:topic"},
            {"text": "Отметить прогресс", "callback_data": "progress:mark"},
        ],
        [
            {"text": "Сложно", "callback_data": "feedback:too_hard"},
            {"text": "Просто", "callback_data": "feedback:too_easy"},
            {"text": "Заменить", "callback_data": "feedback:replace"},
        ],
    ]
    if miniapp_url:
        rows.insert(0, [{"text": "Открыть Mini App", "web_app": {"url": miniapp_url}}])
    return {"inline_keyboard": rows}
