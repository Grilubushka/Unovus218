from bot.application.formatters import profile_from_answers, roadmap_message, topic_message
from bot.application.profile_flow import accept_answer, current_question, empty_session
from bot.domain.roadmap import build_roadmap
from bot.infrastructure.config import Settings
from bot.infrastructure.state_store import JsonStateStore
from bot.infrastructure.telegram_api import TelegramApi
from bot.presentation.keyboards import question_keyboard, roadmap_keyboard


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
        user.clear()
        user["session"] = empty_session()
        store.save_user(chat_id, user)
        send_current_question(api, chat_id, user)
        return

    if text == "/roadmap" and user.get("roadmap"):
        api.send_message(chat_id, roadmap_message(user["roadmap"]), roadmap_keyboard(settings.miniapp_url))
        return

    if text == "/debug":
        api.send_message(
            chat_id,
            "Текущая конфигурация бота:\n"
            f"MINIAPP_URL={settings.miniapp_url}\n"
            f"STATE_FILE={settings.state_file}\n\n"
            "Если Mini App открывает example.com, запущен старый контейнер или в .env старый URL.",
        )
        return

    if "session" not in user:
        api.send_message(chat_id, "Нажми /start, и я соберу профиль для персонального маршрута.")
        return

    finish_or_continue(api, store, settings, chat_id, user, text)


def handle_callback(api: TelegramApi, store: JsonStateStore, settings: Settings, callback: dict) -> None:
    data = callback.get("data", "")
    chat_id = callback["message"]["chat"]["id"]
    user = store.get_user(chat_id)
    api.answer_callback(callback["id"])

    if data.startswith("answer:"):
        answer = data.split(":", 1)[1]
        finish_or_continue(api, store, settings, chat_id, user, answer)
        return

    roadmap = user.get("roadmap")
    if not roadmap:
        api.send_message(chat_id, "Сначала соберём профиль: /start")
        return

    if data == "roadmap:topic":
        api.send_message(chat_id, topic_message(roadmap), roadmap_keyboard(settings.miniapp_url))
    elif data == "progress:mark":
        api.send_message(chat_id, "Готово: текущая тема отмечена как пройденная. В Mini App прогресс пересчитается на карте.")
    elif data == "feedback:too_hard":
        api.send_message(chat_id, "Понял: заменяю материал на более простой и добавляю вводное объяснение.")
    elif data == "feedback:too_easy":
        api.send_message(chat_id, "Понял: предложу более сложную практику и можно будет пропустить часть вводных тем.")
    elif data == "feedback:replace":
        api.send_message(chat_id, "Материал заменён на альтернативный бесплатный русскоязычный источник.")


def finish_or_continue(
    api: TelegramApi,
    store: JsonStateStore,
    settings: Settings,
    chat_id: int,
    user: dict,
    answer: str,
) -> None:
    session = user.setdefault("session", empty_session())
    finished = accept_answer(session, answer)
    if not finished:
        store.save_user(chat_id, user)
        send_current_question(api, chat_id, user)
        return

    profile = profile_from_answers(session["answers"])
    roadmap = build_roadmap(profile)
    user["profile"] = session["answers"]
    user["roadmap"] = roadmap
    user.pop("session", None)
    store.save_user(chat_id, user)
    api.send_message(chat_id, roadmap_message(roadmap), roadmap_keyboard(settings.miniapp_url))


def send_current_question(api: TelegramApi, chat_id: int, user: dict) -> None:
    question = current_question(user["session"])
    if question:
        api.send_message(chat_id, question["text"], question_keyboard(question))


if __name__ == "__main__":
    main()
