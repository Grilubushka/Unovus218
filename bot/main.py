from bot.application.profile_flow import (
    TOTAL_STEPS,
    QuizOption,
    QuizQuestion,
    apply_answer,
    create_manual_option,
    create_multi_option,
    current_question,
    empty_session,
    get_result,
    get_option,
    go_back,
    replace_question_options,
    render_completion,
    render_intro,
    render_question,
    seed_top10_options,
)
from bot.infrastructure.config import Settings
from bot.infrastructure.onboarding_db import OnboardingDatabase
from bot.infrastructure.state_store import JsonStateStore
from bot.infrastructure.telegram_api import TelegramApi
from bot.presentation.keyboards import miniapp_keyboard, question_keyboard, start_keyboard


HTML = "HTML"
BOT_CHAT_ID = "bot_chat_id"
BOT_MESSAGE_ID = "bot_message_id"
DB_SESSION_ID = "db_session_id"
DB_USER_ID = "db_user_id"


def main() -> None:
    settings = Settings()
    settings.validate()
    api = TelegramApi(settings.bot_token)
    store = JsonStateStore(settings.state_file)
    database = OnboardingDatabase(settings.database_path)
    database.connect()
    database.init_schema()
    offset = None
    print(f"Progressors bot started. Onboarding database: {settings.database_path}")

    try:
        while True:
            for update in api.get_updates(offset=offset):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(api, store, database, settings, update["message"])
                elif "callback_query" in update:
                    handle_callback(api, store, database, settings, update["callback_query"])
    finally:
        database.close()


def handle_message(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    message: dict,
) -> None:
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user = store.get_user(chat_id)

    if text in {"/start", "/restart"}:
        abandon_active_session(database, user)
        target = preserved_message_target(user)
        user.clear()
        user.update(target)
        database.upsert_user(message.get("from") or {}, chat_id)
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
            f"DATABASE_PATH={settings.database_path}\n\n"
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

    handle_text_answer(
        api,
        store,
        database,
        settings,
        chat_id,
        user,
        text,
        user_id=telegram_user_id(message.get("from") or {}, chat_id),
    )


def handle_callback(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    callback: dict,
) -> None:
    data = callback.get("data", "")
    chat_id = callback["message"]["chat"]["id"]
    callback_id = callback["id"]
    user = store.get_user(chat_id)

    if data == "quiz:start":
        api.answer_callback(callback_id)
        abandon_active_session(database, user)
        target = preserved_message_target(user)
        user.clear()
        user.update(target)
        telegram_user = callback.get("from") or {}
        user_id = telegram_user_id(telegram_user, chat_id)
        database.upsert_user(telegram_user, user_id)
        session = empty_session()
        session_id = database.create_session(user_id, TOTAL_STEPS, {})
        session[DB_SESSION_ID] = session_id
        session[DB_USER_ID] = user_id
        user["session"] = session
        remember_callback_message(user, callback)
        store.save_user(chat_id, user)
        database.save_event(
            user_id=user_id,
            event_name="quiz_start",
            payload={"source": "inline_button"},
            session_id=session_id,
        )
        send_current_question(api, store, database, chat_id, user)
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
        question = current_question_with_database(session, database)
        if not is_current_step(session, question, answer_step) or question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, database, chat_id, user)
            return

        option = get_option(question, option_code)
        if option is None:
            api.answer_callback(callback_id, "Такого варианта нет.")
            return

        api.answer_callback(callback_id)
        finish_or_continue(
            api,
            store,
            database,
            settings,
            chat_id,
            user,
            question,
            option,
            user_id=telegram_user_id(callback.get("from") or {}, chat_id),
            source="button",
        )
        return

    if data.startswith("quiz:toggle:"):
        parsed = parse_option_callback(data, "toggle")
        if parsed is None:
            api.answer_callback(callback_id)
            return

        answer_step, option_code = parsed
        question = current_question_with_database(session, database)
        if not is_current_step(session, question, answer_step) or not question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, database, chat_id, user)
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
        send_current_question(api, store, database, chat_id, user)
        return

    if data.startswith("quiz:done:"):
        requested_step = parse_step_callback(data, "done")
        question = current_question_with_database(session, database)
        if requested_step is None or not is_current_step(session, question, requested_step) or not question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, database, chat_id, user)
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
        finish_or_continue(
            api,
            store,
            database,
            settings,
            chat_id,
            user,
            question,
            create_multi_option(question, selected_options),
            user_id=telegram_user_id(callback.get("from") or {}, chat_id),
            source="multi_button",
        )
        return

    if data.startswith("quiz:text_clear:"):
        requested_step = parse_step_callback(data, "text_clear")
        question = current_question_with_database(session, database)
        if requested_step is not None and is_current_step(session, question, requested_step):
            session["draft_messages"] = []
            store.save_user(chat_id, user)
            send_current_question(api, store, database, chat_id, user)
        api.answer_callback(callback_id)
        return

    if data.startswith("quiz:back:"):
        requested_step = parse_step_callback(data, "back")
        question = current_question_with_database(session, database)
        if requested_step is None or not is_current_step(session, question, requested_step):
            api.answer_callback(callback_id)
            return
        if not go_back(session):
            api.answer_callback(callback_id, "Назад уже нельзя.")
            return
        sync_database_session(database, session)
        store.save_user(chat_id, user)
        api.answer_callback(callback_id)
        send_current_question(api, store, database, chat_id, user)
        return

    api.answer_callback(callback_id)


def handle_text_answer(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    text: str,
    *,
    user_id: int,
) -> None:
    session = user.setdefault("session", empty_session())
    question = current_question_with_database(session, database)
    if question is None:
        complete_onboarding(api, store, database, settings, chat_id, user, dict(session.get("profile", {})))
        return

    if question.multi_select:
        draft_messages = list(session.get("draft_messages", []))
        if text:
            draft_messages.append(text[:500])
        session["draft_messages"] = draft_messages
        store.save_user(chat_id, user)
        send_current_question(api, store, database, chat_id, user)
        return

    option = create_manual_option(question, text)
    finish_or_continue(
        api,
        store,
        database,
        settings,
        chat_id,
        user,
        question,
        option,
        user_id=user_id,
        source="manual",
    )


def finish_or_continue(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    question: QuizQuestion,
    option: QuizOption,
    *,
    user_id: int,
    source: str,
) -> None:
    session = user.setdefault("session", empty_session())
    current_step = int(session.get("step", 0))
    finished = apply_answer(session, question, option)
    persist_answer(database, session, user_id, current_step, question, option, source)
    if not finished:
        store.save_user(chat_id, user)
        send_current_question(api, store, database, chat_id, user)
        return

    complete_onboarding(api, store, database, settings, chat_id, user, dict(session.get("profile", {})))


def complete_onboarding(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    profile: dict,
) -> None:
    finish_database_session(database, user.get("session") or {}, profile)
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


def send_current_question(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    chat_id: int,
    user: dict,
) -> None:
    session = user["session"]
    question = current_question_with_database(session, database)
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


def current_question_with_database(session: dict, database: OnboardingDatabase) -> QuizQuestion | None:
    question = current_question(session)
    if question is None or int(session.get("step", 0)) != 1:
        return question

    goal_code = dict(session.get("profile", {})).get("goal_code", "skill")
    return replace_question_options(question, build_dynamic_top10_options(database, goal_code))


def build_dynamic_top10_options(database: OnboardingDatabase, goal_code: str) -> tuple[QuizOption, ...]:
    popular_rows = database.get_top_interest_answers(goal_code, limit=10)
    options: list[QuizOption] = [
        QuizOption(
            code=str(row["code"]),
            label=str(row["label"]),
            profile_value=str(row["value"]),
            tone=str(row["tone"]),
        )
        for row in popular_rows
    ]

    seen_codes = {option.code for option in options}
    seen_labels = {option.label.casefold() for option in options}
    for seed_option in seed_top10_options(goal_code):
        if len(options) >= 10:
            break
        if seed_option.code in seen_codes or seed_option.label.casefold() in seen_labels:
            continue
        options.append(seed_option)
        seen_codes.add(seed_option.code)
        seen_labels.add(seed_option.label.casefold())

    return tuple(options[:10])


def persist_answer(
    database: OnboardingDatabase,
    session: dict,
    user_id: int,
    current_step: int,
    question: QuizQuestion,
    option: QuizOption,
    source: str,
) -> None:
    session_id = as_int(session.get(DB_SESSION_ID))
    if session_id is None:
        return

    database.save_answer(
        session_id=session_id,
        user_id=user_id,
        step=current_step + 1,
        question_code=question.code,
        question_title=question.title,
        profile_key=question.profile_key,
        answer_code=option.code,
        answer_label=option.label,
        answer_value=option.profile_value,
        source=source,
    )
    database.update_session(session_id, int(session.get("step", 0)), dict(session.get("profile", {})))
    database.save_event(
        user_id=user_id,
        event_name="question_answered",
        payload={
            "question": question.code,
            "answer": option.code,
            "source": source,
            "step": current_step + 1,
        },
        session_id=session_id,
    )


def finish_database_session(database: OnboardingDatabase, session: dict, profile: dict[str, str]) -> None:
    session_id = as_int(session.get(DB_SESSION_ID))
    if session_id is None:
        return

    database.finish_session(session_id, profile, get_result(profile))
    user_id = as_int(session.get(DB_USER_ID))
    if user_id is not None:
        database.save_event(
            user_id=user_id,
            event_name="quiz_finished",
            payload={"profile": profile},
            session_id=session_id,
        )


def sync_database_session(database: OnboardingDatabase, session: dict) -> None:
    session_id = as_int(session.get(DB_SESSION_ID))
    if session_id is not None:
        database.update_session(session_id, int(session.get("step", 0)), dict(session.get("profile", {})))


def abandon_active_session(database: OnboardingDatabase, user: dict) -> None:
    session = user.get("session") or {}
    database.abandon_session(as_int(session.get(DB_SESSION_ID)))


def telegram_user_id(user: dict, fallback_user_id: int) -> int:
    return int(user.get("id") or fallback_user_id)


def as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
