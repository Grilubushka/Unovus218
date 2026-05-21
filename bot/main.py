import json
import threading
import time
from datetime import datetime, timezone
from html import escape
from urllib import error as urllib_error
from urllib import request as urllib_request

from bot.application.onboarding_adaptation import (
    CompletionAdaptation,
    QuestionAdaptation,
    apply_option_labels,
    build_completion_messages,
    build_question_messages,
    parse_completion_adaptation,
    parse_question_adaptation,
    question_fingerprint,
)
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
    progress_bar,
    recommended_specialties,
    replace_question_options,
    render_completion,
    render_intro,
    render_question,
    seed_top10_options,
)
from bot.application.onboarding_payload import build_admin_onboarding_payload
from bot.infrastructure.config import Settings
from bot.infrastructure.llm_agent import LlmAgentClient
from bot.infrastructure.onboarding_db import OnboardingDatabase
from bot.infrastructure.state_store import JsonStateStore
from bot.infrastructure.telegram_api import TelegramApi
from bot.presentation.keyboards import miniapp_keyboard, question_keyboard, routes_keyboard, start_keyboard


HTML = "HTML"
BOT_CHAT_ID = "bot_chat_id"
BOT_MESSAGE_ID = "bot_message_id"
DB_SESSION_ID = "db_session_id"
DB_USER_ID = "db_user_id"
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
WAIT_BAR_FRAMES = (
    "▰▱▱▱▱▱",
    "▰▰▱▱▱▱",
    "▰▰▰▱▱▱",
    "▱▰▰▰▱▱",
    "▱▱▰▰▰▱",
    "▱▱▱▰▰▰",
    "▱▱▱▱▰▰",
    "▱▱▱▱▱▰",
)


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
        send_miniapp_entry(
            api,
            store,
            settings,
            chat_id,
            user,
            user_id=telegram_user_id(message.get("from") or {}, chat_id),
        )
        return

    if text == "/routes":
        send_routes_page(
            api,
            store,
            database,
            settings,
            chat_id,
            user,
            0,
            user_id=telegram_user_id(message.get("from") or {}, chat_id),
        )
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
            send_miniapp_entry(
                api,
                store,
                settings,
                chat_id,
                user,
                user_id=telegram_user_id(message.get("from") or {}, chat_id),
            )
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
        send_current_question(api, store, database, settings, chat_id, user)
        return

    if data.startswith("routes:"):
        api.answer_callback(callback_id)
        handle_routes_callback(api, store, database, settings, chat_id, user, data, callback)
        return

    session = user.get("session")
    if not session:
        api.answer_callback(callback_id)
        send_miniapp_entry(
            api,
            store,
            settings,
            chat_id,
            user,
            user_id=telegram_user_id(callback.get("from") or {}, chat_id),
        )
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
            send_current_question(api, store, database, settings, chat_id, user)
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
            send_current_question(api, store, database, settings, chat_id, user)
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
        send_current_question(api, store, database, settings, chat_id, user)
        return

    if data.startswith("quiz:done:"):
        requested_step = parse_step_callback(data, "done")
        question = current_question_with_database(session, database)
        if requested_step is None or not is_current_step(session, question, requested_step) or not question.multi_select:
            api.answer_callback(callback_id, "Этот вопрос уже не актуален.")
            send_current_question(api, store, database, settings, chat_id, user)
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
            send_current_question(api, store, database, settings, chat_id, user)
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
        send_current_question(api, store, database, settings, chat_id, user)
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
        send_current_question(api, store, database, settings, chat_id, user)
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
        send_current_question(api, store, database, settings, chat_id, user)
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
    session = user.get("session") or {}
    finish_database_session(database, session, profile)
    session_id = as_int(session.get(DB_SESSION_ID))
    user_id = as_int(session.get(DB_USER_ID)) or chat_id
    route = build_sample_route(profile)
    course_id = database.create_course_session(
        user_id=user_id,
        quiz_session_id=session_id,
        profile=profile,
        route=route,
    )
    answers = database.get_session_answers(session_id) if session_id is not None else []
    snapshot = database.get_session_snapshot(session_id) if session_id is not None else None
    admin_payload = build_admin_onboarding_payload(
        telegram_user_id=user_id,
        chat_id=chat_id,
        quiz_session_id=session_id,
        course_session_id=course_id,
        profile=profile,
        answers=answers,
        route=route,
        user=(snapshot or {}).get("user") or {},
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    database.save_event(
        user_id=user_id,
        event_name="admin_onboarding_payload_prepared",
        payload=admin_payload,
        session_id=session_id,
    )
    submit_admin_onboarding_payload_async(settings, admin_payload)
    user["profile"] = profile
    user["active_route_id"] = course_id
    user["active_route_user_id"] = user_id
    user["admin_onboarding_payload"] = admin_payload
    completion_client = create_llm_client(settings)
    completion_copy = generate_completion_adaptation(
        settings,
        profile,
        client=completion_client,
        api=api,
        store=store,
        chat_id=chat_id,
        user=user,
    )
    if completion_copy is not None:
        user["completion_copy"] = completion_copy.as_render_dict()
    else:
        user.pop("completion_copy", None)
    user.pop("session", None)
    user.pop("roadmap", None)
    store.save_user(chat_id, user)
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_completion(profile, user.get("completion_copy")),
        miniapp_keyboard(settings.miniapp_url, user_id),
        parse_mode=HTML,
    )


def send_current_question(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
) -> None:
    session = user["session"]
    question = current_question_with_database(session, database)
    if question is None:
        return

    index = int(session.get("step", 0))
    cache_hit, adaptation = read_cached_question_adaptation(session, question, index)
    question_client = None
    if not cache_hit:
        question_client = create_llm_client(settings)
        adaptation = get_question_adaptation(
            settings,
            session,
            question,
            index,
            client=question_client,
            api=api,
            store=store,
            chat_id=chat_id,
            user=user,
        )

    display_question = apply_option_labels(question, adaptation)
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_question(
            display_question,
            index,
            list(session.get("selected_options", [])),
            list(session.get("draft_messages", [])),
            adaptation.as_render_dict() if adaptation is not None else None,
        ),
        question_keyboard(
            display_question,
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
    *,
    user_id: int | None = None,
) -> None:
    profile = user.get("profile")
    if not profile:
        send_or_edit(api, store, chat_id, user, "Сначала пройдем короткий онбординг.", start_keyboard())
        return
    owner_id = user_id or as_int(user.get("active_route_user_id")) or chat_id
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_completion(profile, user.get("completion_copy")),
        miniapp_keyboard(settings.miniapp_url, owner_id),
        parse_mode=HTML,
    )


def empty_keyboard() -> dict:
    return {"inline_keyboard": []}


def render_question_thinking(question: QuizQuestion, index: int, frame: int = 0, elapsed_seconds: int = 0) -> str:
    step = index + 1
    spinner = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
    wait_bar = WAIT_BAR_FRAMES[frame % len(WAIT_BAR_FRAMES)]
    return (
        f"{spinner} <b>✨ Настраиваю следующий вопрос</b>\n\n"
        f"💬 <b>{escape(question.title)}</b>\n"
        "Подбираю понятные формулировки и варианты под твои ответы. "
        "Еще пару секунд — и можно двигаться дальше 🌿\n\n"
        f"<code>{wait_bar}</code> · {elapsed_seconds} сек.\n"
        f"<b>Шаг {step}/{TOTAL_STEPS}</b> · готовлю\n"
        f"<b>Прогресс:</b> {progress_bar(index)}"
    )


def render_completion_thinking(profile: dict[str, str], frame: int = 0, elapsed_seconds: int = 0) -> str:
    result = get_result(profile)
    spinner = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
    wait_bar = WAIT_BAR_FRAMES[frame % len(WAIT_BAR_FRAMES)]
    return (
        f"{spinner} <b>🎁 Собираю твой маршрут</b>\n\n"
        f"🏁 <b>{escape(str(result['hero']))}</b>\n"
        "Профиль уже сохранен. Аккуратно собираю цель, темп и первый шаг в финальную карточку. "
        "Скоро покажу готовый результат ✨\n\n"
        f"<code>{wait_bar}</code> · {elapsed_seconds} сек."
    )


def get_question_adaptation(
    settings: Settings,
    session: dict,
    question: QuizQuestion,
    index: int,
    *,
    client: LlmAgentClient | None = None,
    api: TelegramApi | None = None,
    store: JsonStateStore | None = None,
    chat_id: int | None = None,
    user: dict | None = None,
) -> QuestionAdaptation | None:
    cache_hit, cached_adaptation = read_cached_question_adaptation(session, question, index)
    if cache_hit:
        return cached_adaptation

    client = client or create_llm_client(settings)
    if client is None:
        return None

    cache = session.setdefault("presentation_cache", {})
    cache_key = str(index)
    fingerprint = question_fingerprint(question, index, session)
    try:
        messages = build_question_messages(question, index, session)
        if api is not None and chat_id is not None and user is not None:
            content = call_llm_with_progress(
                client,
                messages,
                api=api,
                store=store,
                chat_id=chat_id,
                user=user,
                render_progress=lambda frame, elapsed: render_question_thinking(question, index, frame, elapsed),
                interval_seconds=settings.llm_agent_progress_interval,
            )
        else:
            content = client.chat(messages)
        adaptation = parse_question_adaptation(content, question)
    except Exception as error:
        print(f"LLM question adaptation skipped: {error}")
        cache[cache_key] = {"fingerprint": fingerprint, "copy": None}
        return None

    cache[cache_key] = {
        "fingerprint": fingerprint,
        "copy": adaptation.as_cache_dict() if adaptation is not None else None,
    }
    return adaptation


def read_cached_question_adaptation(
    session: dict,
    question: QuizQuestion,
    index: int,
) -> tuple[bool, QuestionAdaptation | None]:
    cache = session.setdefault("presentation_cache", {})
    cache_key = str(index)
    fingerprint = question_fingerprint(question, index, session)
    cached = cache.get(cache_key)
    if not isinstance(cached, dict) or cached.get("fingerprint") != fingerprint:
        return False, None

    cached_copy = cached.get("copy")
    adaptation = parse_question_adaptation(cached_copy, question) if isinstance(cached_copy, dict) else None
    return True, adaptation


def call_llm_with_progress(
    client: LlmAgentClient,
    messages: list[dict[str, str]],
    *,
    api: TelegramApi,
    store: JsonStateStore | None,
    chat_id: int,
    user: dict,
    render_progress,
    interval_seconds: float,
) -> str:
    result: dict[str, object] = {}
    done = threading.Event()

    def run_request() -> None:
        try:
            result["content"] = client.chat(messages)
        except Exception as error:
            result["error"] = error
        finally:
            done.set()

    thread = threading.Thread(target=run_request, daemon=True)
    thread.start()

    frame = 0
    started_at = time.monotonic()
    interval = max(interval_seconds, 0.8)
    while not done.is_set():
        elapsed_seconds = int(time.monotonic() - started_at)
        try:
            send_or_edit(
                api,
                store,
                chat_id,
                user,
                render_progress(frame, elapsed_seconds),
                empty_keyboard(),
                parse_mode=HTML,
            )
        except Exception as error:
            print(f"LLM progress update skipped: {error}")
        frame += 1
        done.wait(interval)

    if "error" in result:
        error = result["error"]
        if isinstance(error, BaseException):
            raise error
        raise RuntimeError(str(error))

    content = result.get("content")
    if not isinstance(content, str):
        raise RuntimeError("LLM agent returned empty content.")
    return content


def generate_completion_adaptation(
    settings: Settings,
    profile: dict[str, str],
    *,
    client: LlmAgentClient | None = None,
    api: TelegramApi | None = None,
    store: JsonStateStore | None = None,
    chat_id: int | None = None,
    user: dict | None = None,
) -> CompletionAdaptation | None:
    client = client or create_llm_client(settings)
    if client is None:
        return None

    try:
        messages = build_completion_messages(
            profile,
            get_result(profile),
            recommended_specialties(profile) if profile.get("goal_code") == "explore" else [],
        )
        if api is not None and chat_id is not None and user is not None:
            content = call_llm_with_progress(
                client,
                messages,
                api=api,
                store=store,
                chat_id=chat_id,
                user=user,
                render_progress=lambda frame, elapsed: render_completion_thinking(profile, frame, elapsed),
                interval_seconds=settings.llm_agent_progress_interval,
            )
        else:
            content = client.chat(messages)
        return parse_completion_adaptation(content)
    except Exception as error:
        print(f"LLM completion adaptation skipped: {error}")
        return None


def create_llm_client(settings: Settings) -> LlmAgentClient | None:
    token = settings.llm_agent_token.strip()
    if not settings.llm_onboarding_enabled or not settings.llm_agent_base_url.strip():
        return None
    if not token or token == "replace_with_timeweb_agent_token":
        return None
    return LlmAgentClient(
        base_url=settings.llm_agent_base_url,
        token=token,
        model=settings.llm_agent_model,
        timeout=settings.llm_agent_timeout,
        max_tokens=settings.llm_agent_max_tokens,
    )


def submit_admin_onboarding_payload_async(settings: Settings, payload: dict) -> None:
    if not settings.admin_api_base_url:
        return
    thread = threading.Thread(
        target=submit_admin_onboarding_payload,
        args=(settings, payload),
        daemon=True,
    )
    thread.start()


def submit_admin_onboarding_payload(settings: Settings, payload: dict) -> None:
    if not settings.admin_api_base_url:
        return
    if not settings.admin_api_token:
        print("ADMIN_API_BASE_URL is set, but ADMIN_API_TOKEN is empty; skipping Django onboarding submit.")
        return

    url = f"{settings.admin_api_base_url}/api/onboarding/complete"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.admin_api_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=settings.admin_api_timeout) as response:
            response.read()
    except (urllib_error.URLError, TimeoutError, OSError) as error:
        print(f"Failed to submit onboarding payload to Django admin API: {error}")


def handle_routes_callback(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    data: str,
    callback: dict,
) -> None:
    telegram_user = callback.get("from") or {}
    user_id = telegram_user_id(telegram_user, chat_id)
    parts = data.split(":")
    if len(parts) >= 2 and parts[1] == "menu":
        send_miniapp_entry(api, store, settings, chat_id, user, user_id=user_id)
        return

    if len(parts) >= 3 and parts[1] == "page":
        page = as_int(parts[2]) or 0
        send_routes_page(api, store, database, settings, chat_id, user, page, user_id=user_id)
        return

    if len(parts) >= 4 and parts[1] == "detail":
        route_id = as_int(parts[2])
        page = as_int(parts[3]) or 0
        if route_id is not None:
            send_route_detail(api, store, database, settings, chat_id, user, route_id, page, user_id=user_id)
        return

    send_routes_page(api, store, database, settings, chat_id, user, 0, user_id=user_id)


def send_routes_page(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    page: int,
    *,
    user_id: int | None = None,
) -> None:
    owner_id = user_id or chat_id
    routes = database.list_active_routes(owner_id)
    if not routes:
        send_or_edit(
            api,
            store,
            chat_id,
            user,
            "Пока нет активных маршрутов. Пройди онбординг, и я сохраню первый маршрут в базе.",
            start_keyboard(),
        )
        return

    page = min(max(page, 0), len(routes) - 1)
    route = routes[page]
    user["active_route_id"] = route["id"]
    user["active_route_user_id"] = owner_id
    if route.get("profile"):
        user["profile"] = route["profile"]
    store.save_user(chat_id, user)
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_route_page(route, page, len(routes)),
        routes_keyboard(
            page=page,
            total=len(routes),
            miniapp_url=settings.miniapp_url,
            route_id=route["id"],
            telegram_user_id=owner_id,
        ),
        parse_mode=HTML,
    )


def send_route_detail(
    api: TelegramApi,
    store: JsonStateStore,
    database: OnboardingDatabase,
    settings: Settings,
    chat_id: int,
    user: dict,
    route_id: int,
    page: int,
    *,
    user_id: int,
) -> None:
    route = database.get_course_session(route_id, user_id=user_id)
    if route is None:
        send_routes_page(api, store, database, settings, chat_id, user, page, user_id=user_id)
        return

    user["active_route_id"] = route["id"]
    user["active_route_user_id"] = user_id
    if route.get("profile"):
        user["profile"] = route["profile"]
    store.save_user(chat_id, user)
    send_or_edit(
        api,
        store,
        chat_id,
        user,
        render_route_detail(route),
        routes_keyboard(
            page=page,
            total=max(len(database.list_active_routes(user_id)), 1),
            miniapp_url=settings.miniapp_url,
            route_id=route_id,
            telegram_user_id=user_id,
        ),
        parse_mode=HTML,
    )


def render_route_page(route: dict, page: int, total: int) -> str:
    profile = route["profile"]
    modules = route["route"]
    title = route_title(route)
    current_module = int(route.get("current_module") or 0)
    total_modules = max(int(route.get("total_modules") or len(modules) or 1), 1)
    progress = 100 if route.get("status") == "completed" else round(current_module / total_modules * 100)
    next_title = modules[current_module]["title"] if current_module < len(modules) else "маршрут завершён"
    return (
        f"🧭 <b>Мои маршруты</b> · {page + 1}/{total}\n\n"
        f"<b>{escape(title)}</b>\n"
        f"Статус: {escape(str(route.get('status') or 'active'))}\n"
        f"Прогресс: {progress}% · модулей {current_module}/{total_modules}\n"
        f"Цель: {escape(str(profile.get('goal') or 'не указано'))}\n"
        f"Следующий шаг: {escape(str(next_title))}\n\n"
        "Листай маршруты стрелками или открывай выбранный в Mini App."
    )


def render_route_detail(route: dict) -> str:
    modules = route["route"]
    lines = [
        f"🧭 <b>{escape(route_title(route))}</b>",
        "",
        f"ID маршрута: <code>{route['id']}</code>",
        f"Статус: {escape(str(route.get('status') or 'active'))}",
        "",
        "<b>Модули:</b>",
    ]
    for index, module in enumerate(modules, start=1):
        lines.append(f"{index}. {escape(str(module.get('title') or f'Модуль {index}'))}")
        outcome = module.get("outcome") or module.get("description")
        if outcome:
            lines.append(f"   {escape(str(outcome))}")
    return "\n".join(lines)


def route_title(route: dict) -> str:
    profile = route.get("profile") or {}
    if profile.get("interest"):
        return str(profile["interest"]).replace("интересуется ", "").replace("хочет ", "").capitalize()
    modules = route.get("route") or []
    if modules:
        return str(modules[0].get("title") or "Персональный маршрут")
    return "Персональный маршрут"


def build_sample_route(profile: dict[str, str]) -> list[dict]:
    interest = profile.get("interest", "выбранная тема")
    focus = profile.get("focus", "первый результат")
    time = profile.get("time", "комфортный темп")
    level = profile.get("level", "стартовый уровень")
    return [
        {
            "title": "Старт и диагностика",
            "description": f"Уточнить цель: {interest}.",
            "duration": "1 неделя",
            "outcome": f"Понятная стартовая точка с учётом: {level}.",
            "practice": "Собрать короткий список задач, которые хочется уметь решать.",
            "checkpoint": "Сформулирован первый измеримый результат.",
            "skills": ["цель", "диагностика", "план"],
            "materials": [
                sample_material("Статья", "Как определить стартовый уровень", "База знаний Прогрессоров", "15 мин", "Прочитать и отметить знакомые темы."),
                sample_material("Практика", "Мини-аудит навыков", "Рабочий лист", "20 мин", "Заполнить чек-лист и выбрать пробелы."),
            ],
        },
        {
            "title": "База без перегруза",
            "description": f"Закрыть минимум, который нужен под запрос: {focus}.",
            "duration": "1-2 недели",
            "outcome": "Пользователь понимает базовые термины и может повторить простые действия.",
            "practice": "Сделать 3 коротких упражнения по материалам.",
            "checkpoint": "Мини-тест на понимание базовых понятий.",
            "skills": ["база", "практика", "самопроверка"],
            "materials": [
                sample_material("Видео", "Базовое объяснение темы", "Открытый видеокурс", "18 мин", "Посмотреть и выписать 5 ключевых идей."),
                sample_material("Практика", "Тренировка базового действия", "Открытый тренажёр", "30 мин", "Повторить действие по инструкции."),
                sample_material("Мини-тест", "Проверка базы", "Самопроверка", "7 мин", "Ответить на вопросы без подсказок."),
            ],
        },
        {
            "title": "Первый видимый результат",
            "description": f"Собрать результат в режиме: {time}.",
            "duration": "1-2 недели",
            "outcome": "Есть небольшой артефакт, который можно показать или использовать.",
            "practice": "Собрать мини-проект и описать, что получилось.",
            "checkpoint": "Финальная проверка результата по критериям.",
            "skills": ["проект", "рефлексия", "следующий шаг"],
            "materials": [
                sample_material("Практика", "Мини-проект по выбранной теме", "Проектный шаблон", "45 мин", "Собрать результат по шагам."),
                sample_material("Статья", "Как улучшить первый результат", "База знаний Прогрессоров", "12 мин", "Найти 2 улучшения для следующей итерации."),
            ],
        },
    ]


def sample_material(kind: str, title: str, source: str, duration: str, interaction: str) -> dict:
    return {
        "kind": kind,
        "title": title,
        "source": source,
        "duration": duration,
        "interaction": interaction,
    }


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
