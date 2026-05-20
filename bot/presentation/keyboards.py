from bot.application.profile_flow import QuizQuestion


def inline_keyboard(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}


def callback_button(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def start_keyboard() -> dict:
    return inline_keyboard(
        [
            [callback_button("✨ Собрать мой маршрут", "quiz:start")],
        ]
    )


def question_keyboard(
    question: QuizQuestion,
    index: int,
    selected_codes: list[str] | None = None,
    *,
    can_go_back: bool = False,
    draft_messages: list[str] | None = None,
) -> dict:
    selected = set(selected_codes or [])
    draft = draft_messages or []
    buttons: list[dict] = []

    for option in question.options:
        text = f"✅ {option.label}" if question.multi_select and option.code in selected else option.label
        callback_prefix = "quiz:toggle" if question.multi_select else "quiz:answer"
        buttons.append(callback_button(text, f"{callback_prefix}:{index}:{option.code}"))

    columns = 1 if question.profile_key == "level" else max(1, question.keyboard_columns)
    rows = [buttons[position : position + columns] for position in range(0, len(buttons), columns)]
    if draft:
        rows.append([callback_button("Очистить свои варианты", f"quiz:text_clear:{index}")])

    if question.multi_select:
        control_row = []
        if can_go_back:
            control_row.append(callback_button("← Назад", f"quiz:back:{index}"))
        control_row.append(callback_button("Готово", f"quiz:done:{index}"))
        rows.append(control_row)
    elif can_go_back:
        rows.append([callback_button("← Назад", f"quiz:back:{index}")])

    return inline_keyboard(rows)


def miniapp_keyboard(miniapp_url: str) -> dict:
    rows: list[list[dict]] = []
    if miniapp_url:
        rows.append([{"text": "Открыть Mini App", "web_app": {"url": miniapp_url}}])
    rows.append([callback_button("↻ Собрать заново", "quiz:start")])
    return inline_keyboard(rows)
