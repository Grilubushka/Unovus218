from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bot.application.profile_flow import QuizQuestion

MAX_SINGLE_COLUMN_BUTTONS = 5


def inline_keyboard(rows: list[list[dict]]) -> dict:
    return {"inline_keyboard": rows}


def callback_button(text: str, callback_data: str, *, style: str = "primary", emoji: str | None = None) -> dict:
    return {"text": styled_text(text, emoji=emoji), "callback_data": callback_data, "style": style}


def web_app_button(text: str, url: str, *, style: str = "success", emoji: str | None = None) -> dict:
    return {"text": styled_text(text, emoji=emoji), "web_app": {"url": url}, "style": style}


def styled_text(text: str, *, emoji: str | None = None) -> str:
    return f"{emoji} {text}".strip() if emoji else text


def button_rows(buttons: list[dict]) -> list[list[dict]]:
    if len(buttons) <= MAX_SINGLE_COLUMN_BUTTONS:
        return [[button] for button in buttons]
    return [buttons[position : position + 2] for position in range(0, len(buttons), 2)]


def start_keyboard() -> dict:
    return inline_keyboard(
        [
            [callback_button("Собрать мой маршрут", "quiz:start", style="success", emoji="✨")],
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
        buttons.append(callback_button(text, f"{callback_prefix}:{index}:{option.code}", style="primary"))

    rows = button_rows(buttons)
    if draft:
        rows.append([callback_button("Очистить свои варианты", f"quiz:text_clear:{index}", style="danger", emoji="🧹")])

    if question.multi_select:
        control_row = []
        if can_go_back:
            control_row.append(callback_button("Назад", f"quiz:back:{index}", style="danger", emoji="⬅️"))
        control_row.append(callback_button("Готово", f"quiz:done:{index}", style="success", emoji="✅"))
        rows.append(control_row)
    elif can_go_back:
        rows.append([callback_button("Назад", f"quiz:back:{index}", style="danger", emoji="⬅️")])

    return inline_keyboard(rows)


def miniapp_url_for_user(miniapp_url: str, telegram_user_id: int | None = None) -> str:
    if not miniapp_url or telegram_user_id is None:
        return miniapp_url

    parsed = urlsplit(miniapp_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"telegram_user_id", "user_id"}
    ]
    query.append(("telegram_user_id", str(telegram_user_id)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def miniapp_keyboard(miniapp_url: str, telegram_user_id: int | None = None) -> dict:
    buttons: list[dict] = []
    if miniapp_url:
        buttons.append(
            web_app_button(
                "Открыть Mini App",
                miniapp_url_for_user(miniapp_url, telegram_user_id),
                style="success",
                emoji="🚀",
            )
        )
    buttons.append(callback_button("Мои маршруты", "routes:list:0", style="primary", emoji="🧭"))
    buttons.append(callback_button("Собрать заново", "quiz:start", style="primary", emoji="🔄"))
    return inline_keyboard(button_rows(buttons))


def routes_keyboard(
    *,
    page: int,
    total: int,
    miniapp_url: str,
    route_id: int | None = None,
    telegram_user_id: int | None = None,
) -> dict:
    buttons: list[dict] = []
    if miniapp_url:
        buttons.append(
            web_app_button(
                "Открыть в Mini App",
                miniapp_url_for_user(miniapp_url, telegram_user_id),
                style="success",
                emoji="🚀",
            )
        )

    if total > 1:
        buttons.append(callback_button("Назад", f"routes:page:{max(page - 1, 0)}", style="danger", emoji="⬅️"))
        buttons.append(callback_button(f"{page + 1}/{total}", f"routes:page:{page}", style="primary", emoji="📄"))
        buttons.append(callback_button("Дальше", f"routes:page:{min(page + 1, total - 1)}", style="success", emoji="➡️"))

    if route_id is not None:
        buttons.append(callback_button("Подробнее", f"routes:detail:{route_id}:{page}", style="primary", emoji="🔍"))
    buttons.append(callback_button("Главное меню", "routes:menu", style="primary", emoji="🏠"))
    buttons.append(callback_button("Собрать новый", "quiz:start", style="primary", emoji="🔄"))
    return inline_keyboard(button_rows(buttons))
