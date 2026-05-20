from bot.application.profile_flow import (
    QuizOption,
    QuizQuestion,
    apply_answer,
    create_manual_option,
    create_multi_option,
    current_question,
    empty_session,
    get_option,
    go_back,
    render_completion,
    render_intro,
    render_question,
)
from bot.infrastructure.config import Settings
from bot.infrastructure.state_store import JsonStateStore
from bot.infrastructure.telegram_api import TelegramApi
from bot.presentation.keyboards import miniapp_keyboard, question_keyboard, start_keyboard


HTML = "HTML"
BOT_CHAT_ID = "bot_chat_id"
BOT_MESSAGE_ID = "bot_message_id"


def main() -> None:
    settings = Settings()
    settings.validate()
    api = TelegramApi(settings.bot_token)
    store = JsonStateStore(settings.state_file)
    offset = None
    print("Progressors bot started")

    while True:
        for update in api.get_updates(offset=offset):
            offset = update["update_id"] + 1
            if "message" in update:
                handle_message(api, store, settings, update["message"])
            elif "callback_query" in update:
                handle_callback(api, store, settings, update["callback_query"])


def handle_message(api: TelegramApi, store: JsonStateStore, settings: Settings, message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user = store.get_user(chat_id)

    if text in {"/start", "/restart"}:
        target = preserved_message_target(user)
        user.clear()
        user.update(target)
        store.save_user(chat_id, user)
        send_or_edit(api, store, chat_id, user, render_intro(), start_keyboard(), parse_mode=HTML)
        return

    if text in {"/app", "/roadmap"}:
        send_miniapp_entry(api, store, settings, chat_id, user)
        return

    if text == "/debug":
        send_or_edit(
            api,
            store,
            chat_id,
            user,
            "Текущая конфигурация бота:\n"
            f"MINIAPP_URL={settings.miniapp_url}\n"
            f"STATE_FILE={settings.state_file}\n\n"
            "Если Mini App открывает example.com, запущен старый контейнер или в .env старый URL.",
        )
        return

    session = user.get("session")
    if not session:
        if user.get("profile"):
            send_miniapp_entry(api, store, settings, chat_id, user)
            return
        send_or_edit(api, store, chat_id, user, "Нажми /start, и я соберу профиль для Mini App.", start_keyboard())
        return

    handle_text_answer(api, store, settings, chat_id, user, text)


def handle_callback(api: TelegramApi, store: JsonStateStore, settings: Settings, callback: dict) -> None:
    data = callback.get("data", "")
    chat_id = callback["message"]["chat"]["id"]
    callback_id = callback["id"]
    user = store.get_user(chat_id)

    if data == "quiz:start":
        api.answer_callback(callback_id)
        user.clear()
        user["session"] = empty_session()
        remember_callback_message(user, callback)
        store.save_user(chat_id, user)
        send_current_question(api, store, chat_id, user)
        return

    session = user.get("session")
    if not session:
        api.answer_callback(callback_id)
        send_miniapp_entry(api, store, settings, chat_id, user)
        return

    if data.startswith("quiz:answer:"):
        parsed = parse_option_callback(data, "answer")
        if parsed is None:
            api.answer_callback(callback_id)
            return

        answer_step, option_code = parsed
        question = current_question(session)
        if not is_current_step(session, question, answer_step) or question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, chat_id, user)
            return

        option = get_option(question, option_code)
        if option is None:
            api.answer_callback(callback_id, "Такого варианта нет.")
            return

        api.answer_callback(callback_id)
        finish_or_continue(api, store, settings, chat_id, user, question, option)
        return

    if data.startswith("quiz:toggle:"):
        parsed = parse_option_callback(data, "toggle")
        if parsed is None:
            api.answer_callback(callback_id)
            return

        answer_step, option_code = parsed
        question = current_question(session)
        if not is_current_step(session, question, answer_step) or not question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, chat_id, user)
            return

        option = get_option(question, option_code)
        if option is None:
            api.answer_callback(callback_id, "Такого варианта нет.")
            return

        selected_codes = list(session.get("selected_options", []))
        if option.code in selected_codes:
            selected_codes.remove(option.code)
        else:
            selected_codes.append(option.code)

        session["selected_options"] = selected_codes
        store.save_user(chat_id, user)
        api.answer_callback(callback_id)
        send_current_question(api, store, chat_id, user)
        return

    if data.startswith("quiz:done:"):
        requested_step = parse_step_callback(data, "done")
        question = current_question(session)
        if requested_step is None or not is_current_step(session, question, requested_step) or not question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, chat_id, user)
            return

        selected_codes = list(session.get("selected_options", []))
        selected_options = [option for option in question.options if option.code in selected_codes]
        draft_messages = list(session.get("draft_messages", []))
        if draft_messages:
            selected_options.append(create_manual_option(question, "\n".join(draft_messages)))

        if not selected_options:
            api.answer_callback(callback_id, "Выбери хотя бы один вариант или напиши свой.")
            return

        api.answer_callback(callback_id)
        finish_or_continue(api, store, settings, chat_id, user, question, create_multi_option(question, selected_options))
        return

    if data.startswith("quiz:text_clear:"):
        requested_step = parse_step_callback(data, "text_clear")
        question = current_question(session)
        if requested_step is not None and is_current_step(session, question, requested_step):
            session["draft_messages"] = []
            store.save_user(chat_id, user)
            send_current_question(api, store, chat_id, user)
        api.answer_callback(callback_id)
        return

    if data.startswith("quiz:back:"):
        requested_step = parse_step_callback(data, "back")
        question = current_question(session)
        if requested_step is None or not is_current_step(session, question, requested_step):
            api.answer_callback(callback_id)
            return
        if not go_back(session):
            api.answer_callback(callback_id, "Назад уже нельзя.")
            return
        store.save_user(chat_id, user)
        api.answer_callback(callback_id)
        send_current_question(api, store, chat_id, user)
        return

    api.answer_callback(callback_id)


def handle_text_answer(
    api: TelegramApi,
    store: JsonStateStore,
    settings: Settings,
    chat_id: int,
    user: dict,
    text: str,
) -> None:
    session = user.setdefault("session", empty_session())
    question = current_question(session)
    if question is None:
        complete_onboarding(api, store, settings, chat_id, user, dict(session.get("profile", {})))
        return

    if question.multi_select:
        draft_messages = list(session.get("draft_messages", []))
        if text:
            draft_messages.append(text[:500])
        session["draft_messages"] = draft_messages
        store.save_user(chat_id, user)
        send_current_question(api, store, chat_id, user)
        return

    option = create_manual_option(question, text)
    finish_or_continue(api, store, settings, chat_id, user, question, option)


def finish_or_continue(
    api: TelegramApi,
    store: JsonStateStore,
    settings: Settings,
    chat_id: int,
    user: dict,
    question: QuizQuestion,
    option: QuizOption,
) -> None:
    session = user.setdefault("session", empty_session())
    finished = apply_answer(session, question, option)
    if not finished:
        store.save_user(chat_id, user)
        send_current_question(api, store, chat_id, user)
        return

    complete_onboarding(api, store, settings, chat_id, user, dict(session.get("profile", {})))


def complete_onboarding(
    api: TelegramApi,
    store: JsonStateStore,
    settings: Settings,
    chat_id: int,
    user: dict,
    profile: dict,
) -> None:
    user["profile"] = profile
    user.pop("session", None)
    user.pop("roadmap", None)
    store.save_user(chat_id, user)
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_completion(profile),
        miniapp_keyboard(settings.miniapp_url),
        parse_mode=HTML,
    )


def send_current_question(api: TelegramApi, store: JsonStateStore, chat_id: int, user: dict) -> None:
    session = user["session"]
    question = current_question(session)
    if question is None:
        return

    index = int(session.get("step", 0))
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_question(
            question,
            index,
            list(session.get("selected_options", [])),
            list(session.get("draft_messages", [])),
        ),
        question_keyboard(
            question,
            index,
            list(session.get("selected_options", [])),
            can_go_back=index > 0,
            draft_messages=list(session.get("draft_messages", [])),
        ),
        parse_mode=HTML,
    )


def send_miniapp_entry(
    api: TelegramApi,
    store: JsonStateStore,
    settings: Settings,
    chat_id: int,
    user: dict,
) -> None:
    profile = user.get("profile")
    if not profile:
        send_or_edit(api, store, chat_id, user, "Сначала пройдем короткий онбординг.", start_keyboard())
        return
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_completion(profile),
        miniapp_keyboard(settings.miniapp_url),
        parse_mode=HTML,
    )


def send_or_edit(
    api: TelegramApi,
    store: JsonStateStore | None,
    chat_id: int,
    user: dict,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = None,
    *,
    force_new: bool = False,
) -> None:
    target_chat_id = user.get(BOT_CHAT_ID)
    target_message_id = user.get(BOT_MESSAGE_ID)

    if not force_new and target_chat_id is not None and target_message_id is not None:
        try:
            result = api.edit_message_text(
                int(target_chat_id),
                int(target_message_id),
                text,
                reply_markup,
                parse_mode=parse_mode,
            )
            remember_bot_message(user, result)
            if store is not None:
                store.save_user(chat_id, user)
            return
        except RuntimeError as error:
            if "message is not modified" in str(error).lower():
                return

    result = api.send_message(chat_id, text, reply_markup, parse_mode=parse_mode)
    remember_bot_message(user, result)
    if store is not None:
        store.save_user(chat_id, user)


def preserved_message_target(user: dict) -> dict:
    return {
        key: user[key]
        for key in (BOT_CHAT_ID, BOT_MESSAGE_ID)
        if key in user
    }


def remember_callback_message(user: dict, callback: dict) -> None:
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is not None and message_id is not None:
        user[BOT_CHAT_ID] = chat_id
        user[BOT_MESSAGE_ID] = message_id


def remember_bot_message(user: dict, message: dict) -> None:
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if chat_id is not None and message_id is not None:
        user[BOT_CHAT_ID] = chat_id
        user[BOT_MESSAGE_ID] = message_id


def parse_option_callback(data: str, action: str) -> tuple[int, str] | None:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "quiz" or parts[1] != action:
        return None
    try:
        return int(parts[2]), parts[3]
    except ValueError:
        return None


def parse_step_callback(data: str, action: str) -> int | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "quiz" or parts[1] != action:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def is_current_step(session: dict, question: QuizQuestion | None, answer_step: int) -> bool:
    return question is not None and answer_step == int(session.get("step", 0))


if __name__ == "__main__":
    main()
