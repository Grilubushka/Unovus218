"""Хендлеры Telegram-сценария: старт, ответы, ручной ввод и построение результата."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

from bot.analytics import track_event
from bot.course import (
    build_course,
    deserialize_course,
    make_certificate_code,
    serialize_course,
)
from bot.db import Database
from bot.quiz import (
    BUILD_MESSAGES,
    TOTAL_STEPS,
    QuizOption,
    QuizQuestion,
    create_manual_option,
    create_multi_option,
    get_result,
    get_option,
    get_question,
    replace_question_options,
    seed_top10_options,
)
from bot.ui import (
    certificates_gallery_keyboard,
    certificates_keyboard,
    certificates_menu_keyboard,
    completed_course_keyboard,
    course_menu_keyboard,
    course_module_keyboard,
    question_keyboard,
    render_building,
    render_certificate_saved,
    render_certificates_help,
    render_certificates_list,
    render_certificates_menu,
    render_course_certificate,
    render_course_feedback_ack,
    render_course_menu,
    render_course_module,
    render_intro,
    render_question,
    render_result,
    result_keyboard,
    start_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


class QuizState(StatesGroup):
    """Состояния FSM: бот помнит шаг и ответы пользователя между callback-запросами."""

    answering = State()
    building = State()
    finished = State()


class CourseState(StatesGroup):
    """Состояния прохождения чатового курса после онбординга."""

    ready = State()
    in_progress = State()
    completed = State()


@router.message(Command("start"))
async def handle_start(message: Message, state: FSMContext, db: Database) -> None:
    """Отправляет первый экран теста и очищает старые ответы пользователя."""

    data = await state.get_data()
    await db.abandon_session(data.get("session_id"))
    await db.upsert_user(message.from_user)
    await state.clear()
    await track_event(message.from_user.id, "quiz_start", {"source": "command_start"}, db=db)
    bot_message = await message.answer(render_intro(), reply_markup=start_keyboard())
    await state.update_data(chat_id=bot_message.chat.id, bot_message_id=bot_message.message_id)


@router.message(Command("restart"))
async def handle_restart(message: Message, state: FSMContext, db: Database) -> None:
    """Позволяет начать тест заново командой, если пользователь потерял старое сообщение."""

    data = await state.get_data()
    await db.abandon_session(data.get("session_id"))
    await db.upsert_user(message.from_user)
    await state.clear()
    await track_event(message.from_user.id, "quiz_restart", {"source": "command_restart"}, db=db)
    bot_message = await message.answer(render_intro(), reply_markup=start_keyboard())
    await state.update_data(chat_id=bot_message.chat.id, bot_message_id=bot_message.message_id)


@router.callback_query(F.data == "quiz:start")
async def handle_quiz_start(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Запускает первый вопрос и дальше работает через редактирование этого же сообщения."""

    await callback.answer()
    if callback.message is None:
        return

    old_data = await state.get_data()
    await db.abandon_session(old_data.get("session_id"))
    await db.upsert_user(callback.from_user)
    session_id = await db.create_session(callback.from_user.id, TOTAL_STEPS, {})

    await state.set_state(QuizState.answering)
    await state.update_data(
        step=0,
        profile={},
        session_id=session_id,
        selected_options=[],
        draft_messages=[],
        history=[],
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
    )
    await track_event(
        callback.from_user.id,
        "quiz_start",
        {"source": "inline_button"},
        db=db,
        session_id=session_id,
    )

    question = await build_question(0, {}, db)
    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_question(question, 0),
        question_keyboard(question, 0),
    )


@router.callback_query(F.data.startswith("quiz:answer:"))
async def handle_button_answer(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Сохраняет ответ из inline-кнопки и переключает пользователя на следующий экран."""

    await callback.answer()

    data = await state.get_data()
    current_step = int(data.get("step", 0))
    profile: dict[str, str] = data.get("profile", {})
    session_id = data.get("session_id")

    parsed = (callback.data or "").split(":")
    if len(parsed) != 4:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    _, _, raw_step, option_code = parsed
    try:
        answer_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    if answer_step != current_step or answer_step >= TOTAL_STEPS:
        await track_event(
            callback.from_user.id,
            "quiz_answer_ignored",
            {"answer_step": answer_step, "current_step": current_step},
            db=db,
            session_id=session_id,
        )
        return

    question = await build_question(answer_step, profile, db)
    if question.multi_select:
        await track_event(
            callback.from_user.id,
            "quiz_answer_ignored",
            {"reason": "multi_select_requires_toggle", "question": question.code},
            db=db,
            session_id=session_id,
        )
        return

    option = get_option(question, option_code)
    if option is None:
        await track_event(
            callback.from_user.id,
            "quiz_answer_invalid",
            {"question": question.code, "option": option_code},
            db=db,
            session_id=session_id,
        )
        return

    await save_answer_and_advance(
        bot=bot,
        db=db,
        state=state,
        user_id=callback.from_user.id,
        data=data,
        question=question,
        option=option,
        source="button",
    )


@router.callback_query(F.data.startswith("quiz:toggle:"))
async def handle_multi_toggle(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Переключает один вариант в мультивыборе и редактирует текущую клавиатуру."""

    await callback.answer()

    data = await state.get_data()
    profile: dict[str, str] = data.get("profile", {})
    current_step = int(data.get("step", 0))
    session_id = data.get("session_id")
    parsed = (callback.data or "").split(":")

    if len(parsed) != 4:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    _, _, raw_step, option_code = parsed
    try:
        answer_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    question = await build_question(answer_step, profile, db)
    if answer_step != current_step or answer_step >= TOTAL_STEPS or not question.multi_select:
        await track_event(
            callback.from_user.id,
            "multi_toggle_ignored",
            {"answer_step": answer_step, "current_step": current_step, "question": question.code},
            db=db,
            session_id=session_id,
        )
        return

    option = get_option(question, option_code)
    if option is None:
        await track_event(
            callback.from_user.id,
            "quiz_answer_invalid",
            {"question": question.code, "option": option_code},
            db=db,
            session_id=session_id,
        )
        return

    chat_id, bot_message_id = resolve_message_target(data, callback.message)
    if chat_id is None or bot_message_id is None:
        return

    selected_codes: list[str] = list(data.get("selected_options", []))
    if option.code in selected_codes:
        selected_codes.remove(option.code)
        action = "removed"
    else:
        selected_codes.append(option.code)
        action = "added"

    await state.update_data(selected_options=selected_codes)
    await track_event(
        callback.from_user.id,
        "multi_option_toggled",
        {"question": question.code, "option": option.code, "action": action, "selected": selected_codes},
        db=db,
        session_id=session_id,
    )
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_question(question, answer_step, selected_codes, list(data.get("draft_messages", []))),
        question_keyboard(
            question,
            answer_step,
            selected_codes,
            can_go_back=answer_step > 0,
            draft_messages=list(data.get("draft_messages", [])),
        ),
    )


@router.callback_query(F.data.startswith("quiz:done:"))
async def handle_multi_done(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Завершает мультивыбор и сохраняет выбранные варианты одним ответом."""

    data = await state.get_data()
    profile: dict[str, str] = data.get("profile", {})
    current_step = int(data.get("step", 0))
    session_id = data.get("session_id")
    raw_step = (callback.data or "").split(":")[-1]

    try:
        requested_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    question = await build_question(current_step, profile, db)
    if requested_step != current_step or requested_step >= TOTAL_STEPS or not question.multi_select:
        await track_event(
            callback.from_user.id,
            "multi_done_ignored",
            {"requested_step": requested_step, "current_step": current_step},
            db=db,
            session_id=session_id,
        )
        return

    selected_codes: list[str] = list(data.get("selected_options", []))
    selected_options = [option for option in question.options if option.code in selected_codes]
    draft_messages: list[str] = list(data.get("draft_messages", []))
    if draft_messages:
        selected_options.append(create_manual_option(question, "\n".join(draft_messages)))

    if not selected_options:
        await callback.answer("Выбери хотя бы один вариант или напиши свой.", show_alert=False)
        return

    await callback.answer()
    await save_answer_and_advance(
        bot=bot,
        db=db,
        state=state,
        user_id=callback.from_user.id,
        data=data,
        question=question,
        option=create_multi_option(question, selected_options),
        source="multi_button",
    )


@router.callback_query(F.data.startswith("quiz:text_done:"))
async def handle_text_done(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
) -> None:
    """Сохраняет накопленный ручной ввод и переводит пользователя дальше."""

    data = await state.get_data()
    current_step = int(data.get("step", 0))
    profile: dict[str, str] = data.get("profile", {})
    session_id = data.get("session_id")
    raw_step = (callback.data or "").split(":")[-1]

    try:
        requested_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    if requested_step != current_step:
        await callback.answer()
        return

    draft_messages: list[str] = list(data.get("draft_messages", []))
    if not draft_messages:
        await callback.answer("Сначала напиши ответ сообщением.", show_alert=False)
        return

    await callback.answer()
    question = await build_question(current_step, profile, db)
    raw_text = "\n".join(draft_messages)
    option = create_manual_option(question, raw_text)
    await track_event(
        callback.from_user.id,
        "manual_answer_received",
        {"question": question.code, "message_count": len(draft_messages), "step": current_step + 1},
        db=db,
        session_id=session_id,
    )
    await save_answer_and_advance(
        bot=bot,
        db=db,
        state=state,
        user_id=callback.from_user.id,
        data=data,
        question=question,
        option=option,
        source="manual",
    )


@router.callback_query(F.data.startswith("quiz:text_clear:"))
async def handle_text_clear(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Очищает накопленный ручной ввод на текущем шаге."""

    await callback.answer()
    data = await state.get_data()
    current_step = int(data.get("step", 0))
    profile: dict[str, str] = data.get("profile", {})
    selected_codes: list[str] = list(data.get("selected_options", []))
    session_id = data.get("session_id")
    raw_step = (callback.data or "").split(":")[-1]

    try:
        requested_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    if requested_step != current_step:
        return

    chat_id, bot_message_id = resolve_message_target(data, callback.message)
    if chat_id is None or bot_message_id is None:
        return

    await state.update_data(draft_messages=[])
    question = await build_question(current_step, profile, db)
    await track_event(
        callback.from_user.id,
        "manual_draft_cleared",
        {"question": question.code, "step": current_step + 1},
        db=db,
        session_id=session_id,
    )
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_question(question, current_step, selected_codes, []),
        question_keyboard(question, current_step, selected_codes, can_go_back=current_step > 0),
    )


@router.callback_query(F.data.startswith("quiz:back:"))
async def handle_back(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Возвращает пользователя на предыдущий вопрос и восстанавливает профиль до прошлого шага."""

    await callback.answer()
    data = await state.get_data()
    current_step = int(data.get("step", 0))
    session_id = data.get("session_id")
    raw_step = (callback.data or "").split(":")[-1]

    try:
        requested_step = int(raw_step)
    except ValueError:
        await track_event(
            callback.from_user.id,
            "quiz_callback_invalid",
            {"callback_data": callback.data},
            db=db,
            session_id=session_id,
        )
        return

    history: list[dict[str, Any]] = list(data.get("history", []))
    if requested_step != current_step or not history:
        return

    previous = history.pop()
    previous_step = int(previous.get("step", max(current_step - 1, 0)))
    previous_profile = dict(previous.get("profile", {}))
    chat_id, bot_message_id = resolve_message_target(data, callback.message)
    if chat_id is None or bot_message_id is None:
        return

    await state.update_data(
        step=previous_step,
        profile=previous_profile,
        selected_options=[],
        draft_messages=[],
        history=history,
    )
    if session_id is not None:
        await db.update_session(session_id, previous_step, previous_profile)

    question = await build_question(previous_step, previous_profile, db)
    await track_event(
        callback.from_user.id,
        "question_back",
        {"from_step": current_step + 1, "to_step": previous_step + 1},
        db=db,
        session_id=session_id,
    )
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_question(question, previous_step),
        question_keyboard(question, previous_step, can_go_back=previous_step > 0),
    )


@router.message(QuizState.answering, F.text, ~F.text.startswith("/"))
async def handle_text_answer(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Сохраняет ручной ответ: сразу для одиночного вопроса, как свой вариант для мультивыбора."""

    raw_text = (message.text or "").strip()
    if not raw_text or raw_text.startswith("/"):
        return

    data = await state.get_data()
    current_step = int(data.get("step", 0))
    profile: dict[str, str] = data.get("profile", {})
    session_id = data.get("session_id")
    selected_codes: list[str] = list(data.get("selected_options", []))
    draft_messages: list[str] = list(data.get("draft_messages", []))
    question = await build_question(current_step, profile, db)
    chat_id, bot_message_id = resolve_message_target(data)
    if chat_id is None or bot_message_id is None:
        logger.warning("Не удалось найти сообщение бота для редактирования.")
        return

    await delete_user_message(bot, message, db, session_id)
    if not question.multi_select:
        option = create_manual_option(question, raw_text)
        await track_event(
            message.from_user.id,
            "manual_answer_received",
            {"question": question.code, "message_count": 1, "step": current_step + 1},
            db=db,
            session_id=session_id,
        )
        await save_answer_and_advance(
            bot=bot,
            db=db,
            state=state,
            user_id=message.from_user.id,
            data=data,
            question=question,
            option=option,
            source="manual",
        )
        return

    draft_messages.append(raw_text[:500])
    await state.update_data(draft_messages=draft_messages)
    await track_event(
        message.from_user.id,
        "manual_message_received",
        {"question": question.code, "message_count": len(draft_messages), "step": current_step + 1},
        db=db,
        session_id=session_id,
    )
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_question(question, current_step, selected_codes, draft_messages),
        question_keyboard(
            question,
            current_step,
            selected_codes,
            can_go_back=current_step > 0,
            draft_messages=draft_messages,
        ),
    )


@router.callback_query(F.data.startswith("course:start:"))
async def handle_course_start(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Создает чатовый курс после онбординга и редактирует центральное меню."""

    await callback.answer()
    if callback.message is None:
        return

    raw_session_id = (callback.data or "").split(":")[-1]
    quiz_session_id = _parse_positive_int(raw_session_id)
    data = await state.get_data()
    profile: dict[str, str] = dict(data.get("profile", {}))

    if not profile and quiz_session_id is not None:
        snapshot = await db.get_session_snapshot(quiz_session_id)
        if snapshot is not None:
            profile = dict(snapshot["profile"])

    if not profile:
        await edit_quiz_message(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "Не нашел сохраненный портрет. Запусти /restart и пройди онбординг заново.",
            start_keyboard(),
        )
        return

    modules = build_course(profile)
    course_id = await db.create_course_session(
        user_id=callback.from_user.id,
        quiz_session_id=quiz_session_id,
        profile=profile,
        route=serialize_course(modules),
    )
    await db.save_course_event(
        course_id=course_id,
        user_id=callback.from_user.id,
        module_index=0,
        event_name="course_started",
        payload={"total_modules": len(modules), "quiz_session_id": quiz_session_id},
    )
    await state.set_state(CourseState.in_progress)
    await state.update_data(
        course_id=course_id,
        current_module=0,
        course_total=len(modules),
        profile=profile,
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
    )

    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_course_menu(
            profile,
            course_id=course_id,
            current_module=0,
            total_modules=len(modules),
            notice="🚀 Курс начался. Первый модуль открыт из центрального меню.",
        ),
        course_menu_keyboard(course_id=course_id, current_module=0, total_modules=len(modules)),
    )


@router.callback_query(F.data == "menu:home")
async def handle_home_menu(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Возвращает на центральное меню из служебных экранов без создания сообщений."""

    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    if course_id is not None:
        course = await db.get_course_session(course_id)
        if course is not None and int(course["telegram_user_id"]) == callback.from_user.id:
            await edit_course_menu(
                bot=bot,
                chat_id=callback.message.chat.id,
                bot_message_id=callback.message.message_id,
                course=course,
            )
            return

    profile: dict[str, str] = dict(data.get("profile", {}))
    if not profile:
        await edit_quiz_message(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_intro(),
            start_keyboard(),
        )
        return

    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_result(profile),
        result_keyboard(_parse_positive_int(str(data.get("session_id", "")))),
    )


@router.callback_query(F.data.startswith("course:menu:"))
async def handle_course_menu(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Возвращает пользователя из любого экрана курса в центральное меню."""

    await callback.answer()
    if callback.message is None:
        return

    course_id = _parse_positive_int((callback.data or "").split(":")[-1])
    if course_id is None:
        return

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != callback.from_user.id:
        await callback.answer("Этот маршрут не найден.", show_alert=False)
        return

    await state.update_data(
        course_id=course_id,
        current_module=int(course["current_module"]),
        course_total=int(course["total_modules"]),
        profile=dict(course["profile"]),
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
    )
    await edit_course_menu(
        bot=bot,
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
        course=course,
    )


@router.callback_query(F.data.startswith("course:module:"))
async def handle_course_module(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Открывает текущий модуль внутри центрального сообщения."""

    await callback.answer()
    if callback.message is None:
        return

    parsed = (callback.data or "").split(":")
    if len(parsed) != 4:
        return

    _, _, raw_course_id, raw_module_index = parsed
    course_id = _parse_positive_int(raw_course_id)
    module_index = _parse_non_negative_int(raw_module_index)
    if course_id is None or module_index is None:
        return

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != callback.from_user.id:
        await callback.answer("Этот маршрут не найден.", show_alert=False)
        return

    modules = deserialize_course(course["route"])
    current_module = int(course["current_module"])
    if course["status"] == "completed":
        await edit_quiz_message(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_course_certificate(
                course["profile"],
                course_id=course_id,
                certificate_code=str(course["certificate_code"]),
                total_modules=len(modules) or int(course["total_modules"]),
            ),
            completed_course_keyboard(course_id),
        )
        return

    if module_index != current_module or module_index >= len(modules):
        await callback.answer("Открой актуальный модуль из центрального меню.", show_alert=False)
        return

    await state.set_state(CourseState.in_progress)
    await state.update_data(
        course_id=course_id,
        current_module=module_index,
        course_total=len(modules),
        profile=dict(course["profile"]),
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
    )
    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_course_module(modules[module_index], module_index, len(modules)),
        course_module_keyboard(course_id, module_index),
    )


@router.callback_query(F.data.startswith("course:certificate:"))
async def handle_course_certificate(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Открывает сертификат завершенного курса внутри центрального сообщения."""

    await callback.answer()
    if callback.message is None:
        return

    course_id = _parse_positive_int((callback.data or "").split(":")[-1])
    if course_id is None:
        return

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != callback.from_user.id:
        await callback.answer("Этот маршрут не найден.", show_alert=False)
        return
    if course["status"] != "completed" or not course["certificate_code"]:
        await callback.answer("Сертификат появится после прохождения всех модулей.", show_alert=False)
        return

    modules = deserialize_course(course["route"])
    await state.update_data(
        course_id=course_id,
        current_module=int(course["current_module"]),
        course_total=len(modules) or int(course["total_modules"]),
        profile=dict(course["profile"]),
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
    )
    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_course_certificate(
            course["profile"],
            course_id=course_id,
            certificate_code=str(course["certificate_code"]),
            total_modules=len(modules) or int(course["total_modules"]),
        ),
        completed_course_keyboard(course_id),
    )


@router.callback_query(F.data.startswith("course:feedback:"))
async def handle_course_feedback(callback: CallbackQuery, db: Database) -> None:
    """Сохраняет обратную связь по текущему модулю."""

    parsed = (callback.data or "").split(":")
    if len(parsed) != 5:
        await callback.answer()
        return

    _, _, raw_course_id, raw_module_index, feedback_code = parsed
    course_id = _parse_positive_int(raw_course_id)
    module_index = _parse_non_negative_int(raw_module_index)
    if course_id is None or module_index is None:
        await callback.answer()
        return

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != callback.from_user.id:
        await callback.answer("Этот маршрут не найден.", show_alert=False)
        return

    await db.save_course_event(
        course_id=course_id,
        user_id=callback.from_user.id,
        module_index=module_index,
        event_name="module_feedback",
        payload={"feedback": feedback_code},
    )
    await callback.answer(render_course_feedback_ack(feedback_code), show_alert=False)


@router.callback_query(F.data.startswith("course:complete:"))
async def handle_course_complete(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Отмечает модуль пройденным и отправляет следующий шаг или сертификат."""

    await callback.answer()
    if callback.message is None:
        return

    parsed = (callback.data or "").split(":")
    if len(parsed) != 4:
        return

    _, _, raw_course_id, raw_module_index = parsed
    course_id = _parse_positive_int(raw_course_id)
    module_index = _parse_non_negative_int(raw_module_index)
    if course_id is None or module_index is None:
        return

    await complete_course_module(
        bot=bot,
        chat_id=callback.message.chat.id,
        bot_message_id=callback.message.message_id,
        state=state,
        db=db,
        user_id=callback.from_user.id,
        course_id=course_id,
        module_index=module_index,
    )


@router.message(CourseState.in_progress, F.text, ~F.text.startswith("/"))
async def handle_course_text(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Позволяет пройти модуль фразой вроде 'модуль пройден'."""

    raw_text = (message.text or "").strip().casefold()
    if not raw_text or raw_text.startswith("/"):
        return

    data = await state.get_data()
    completion_markers = ("модуль пройден", "пройден", "готово", "готов", "дальше", "следующий")
    if not any(marker in raw_text for marker in completion_markers):
        await delete_user_message(bot, message, db, data.get("session_id"))
        await edit_current_course_screen(
            bot=bot,
            state=state,
            db=db,
            user_id=message.from_user.id,
            notice="Чтобы двигаться по курсу, нажми кнопку под модулем или напиши «модуль пройден».",
        )
        return

    course_id = _parse_positive_int(str(data.get("course_id", "")))
    module_index = _parse_non_negative_int(str(data.get("current_module", "")))
    chat_id, bot_message_id = resolve_message_target(data)
    if course_id is None or module_index is None:
        await delete_user_message(bot, message, db, data.get("session_id"))
        return
    if chat_id is None or bot_message_id is None:
        await delete_user_message(bot, message, db, data.get("session_id"))
        return

    await delete_user_message(bot, message, db, data.get("session_id"))

    await complete_course_module(
        bot=bot,
        chat_id=chat_id,
        bot_message_id=bot_message_id,
        state=state,
        db=db,
        user_id=message.from_user.id,
        course_id=course_id,
        module_index=module_index,
    )


@router.message(Command("certificates"))
async def handle_certificates_command(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Открывает раздел сертификатов через редактирование центрального сообщения."""

    certificates = await db.list_user_certificates(message.from_user.id)
    data = await state.get_data()
    chat_id, bot_message_id = resolve_message_target(data)
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    gallery_message_ids = list(data.get("certificate_message_ids", []))
    if gallery_message_ids:
        await delete_user_message(bot, message, db, data.get("session_id"))
        await delete_gallery_messages(bot, message.chat.id, gallery_message_ids)
        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=render_certificates_menu(len(certificates)),
            reply_markup=certificates_menu_keyboard(course_id),
        )
        await state.update_data(
            chat_id=message.chat.id,
            bot_message_id=sent.message_id,
            certificate_message_ids=[],
        )
        return

    if chat_id is None or bot_message_id is None:
        await delete_user_message(bot, message, db, data.get("session_id"))
        return

    await delete_user_message(bot, message, db, data.get("session_id"))
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_certificates_menu(len(certificates)),
        certificates_menu_keyboard(course_id),
    )


@router.callback_query(F.data == "certificates:menu")
async def handle_certificates_menu(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Открывает главный экран сертификатов."""

    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    certificates = await db.list_user_certificates(callback.from_user.id)
    await edit_quiz_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        render_certificates_menu(len(certificates)),
        certificates_menu_keyboard(course_id),
    )


@router.callback_query(F.data == "certificates:upload")
async def handle_certificates_upload_hint(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Подсказывает пользователю, как загрузить сертификат файлом."""

    await callback.answer()
    if callback.message is not None:
        data = await state.get_data()
        course_id = _parse_positive_int(str(data.get("course_id", "")))
        await edit_quiz_message(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            render_certificates_help(),
            certificates_menu_keyboard(course_id),
        )


@router.callback_query(F.data.startswith("certificates:list"))
async def handle_certificates_list(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Показывает последние загруженные сертификаты."""

    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    certificates = await db.list_user_certificates(callback.from_user.id)
    await open_certificates_gallery(
        bot=bot,
        state=state,
        db=db,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        old_message_id=callback.message.message_id,
        certificates=certificates,
        page=0,
        course_id=course_id,
    )


@router.callback_query(F.data.startswith("certificates:page:"))
async def handle_certificates_page(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Переключает страницу галереи сертификатов."""

    await callback.answer()
    if callback.message is None:
        return

    page = _parse_non_negative_int((callback.data or "").split(":")[-1]) or 0
    data = await state.get_data()
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    certificates = await db.list_user_certificates(callback.from_user.id)
    await delete_gallery_messages(bot, callback.message.chat.id, list(data.get("certificate_message_ids", [])))
    await send_certificates_gallery(
        bot=bot,
        state=state,
        chat_id=callback.message.chat.id,
        certificates=certificates,
        page=page,
        course_id=course_id,
    )


@router.callback_query(F.data == "certificates:back")
async def handle_certificates_back(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    """Удаляет галерею сертификатов и восстанавливает центральное меню новым сообщением."""

    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    await delete_gallery_messages(bot, callback.message.chat.id, list(data.get("certificate_message_ids", [])))
    await send_home_message(
        bot=bot,
        state=state,
        db=db,
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
    )


@router.message(F.document | F.photo)
async def handle_certificate_upload(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Сохраняет присланный сертификат и редактирует центральное сообщение."""

    await db.upsert_user(message.from_user)
    data = await state.get_data()
    chat_id, bot_message_id = resolve_message_target(data)
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    saved = await save_uploaded_certificate(message, bot, db)
    certificates = await db.list_user_certificates(message.from_user.id)
    await delete_user_message(bot, message, db, data.get("session_id"))
    gallery_message_ids = list(data.get("certificate_message_ids", []))
    if gallery_message_ids:
        await delete_gallery_messages(bot, message.chat.id, gallery_message_ids)
        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=render_certificate_saved(saved, certificates),
            reply_markup=certificates_menu_keyboard(course_id),
        )
        await state.update_data(
            chat_id=message.chat.id,
            bot_message_id=sent.message_id,
            certificate_message_ids=[],
        )
        return

    if chat_id is None or bot_message_id is None:
        return

    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_certificate_saved(saved, certificates),
        certificates_menu_keyboard(course_id),
    )


async def save_answer_and_advance(
    *,
    bot: Bot,
    db: Database,
    state: FSMContext,
    user_id: int,
    data: dict[str, Any],
    question: QuizQuestion,
    option: QuizOption,
    source: str,
) -> None:
    """Единообразно сохраняет ответ из кнопки или ручного ввода и двигает сценарий дальше."""

    current_step = int(data.get("step", 0))
    profile: dict[str, str] = data.get("profile", {})
    session_id = data.get("session_id")
    chat_id, bot_message_id = resolve_message_target(data)
    if chat_id is None or bot_message_id is None:
        logger.warning("Не удалось найти сообщение бота для редактирования.")
        return

    history: list[dict[str, Any]] = list(data.get("history", []))
    history.append({"step": current_step, "profile": dict(profile)})

    profile[question.profile_key] = option.profile_value
    profile[f"{question.profile_key}_code"] = option.code
    profile[f"{question.profile_key}_tone"] = option.tone

    await track_event(
        user_id,
        "question_answered",
        {
            "question": question.code,
            "answer": option.code,
            "source": source,
            "step": current_step + 1,
        },
        db=db,
        session_id=session_id,
    )
    await track_event(
        user_id,
        f"{question.profile_key}_collected",
        {"value": option.profile_value, "source": source},
        db=db,
        session_id=session_id,
    )

    next_step = current_step + 1
    await state.update_data(
        step=next_step,
        profile=profile,
        selected_options=[],
        draft_messages=[],
        history=history,
    )
    if session_id is not None:
        await db.save_answer(
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
        await db.update_session(session_id, next_step, profile)

    if next_step < TOTAL_STEPS:
        next_question = await build_question(next_step, profile, db)
        await edit_quiz_message(
            bot,
            chat_id,
            bot_message_id,
            render_question(next_question, next_step),
            question_keyboard(next_question, next_step, [], can_go_back=next_step > 0),
        )
        return

    await show_building_and_result(bot, db, chat_id, bot_message_id, state, user_id, profile, session_id)


async def show_building_and_result(
    bot: Bot,
    db: Database,
    chat_id: int,
    bot_message_id: int,
    state: FSMContext,
    user_id: int,
    profile: dict[str, str],
    session_id: int | None,
) -> None:
    """Показывает 2-3 секунды обработки и затем финальный герой-роадмап."""

    await state.set_state(QuizState.building)
    await track_event(user_id, "offer_timer_started", {"duration_seconds": 2.4}, db=db, session_id=session_id)
    await track_event(user_id, "build_started", {"profile": profile}, db=db, session_id=session_id)

    for index, message in enumerate(BUILD_MESSAGES, start=1):
        await edit_quiz_message(bot, chat_id, bot_message_id, render_building(message), None)
        await track_event(
            user_id,
            "build_step_shown",
            {"step": index, "message": message},
            db=db,
            session_id=session_id,
        )
        await asyncio.sleep(0.8)

    result = get_result(profile)
    if session_id is not None:
        await db.finish_session(session_id, profile, result)

    await state.set_state(CourseState.ready)
    await edit_quiz_message(bot, chat_id, bot_message_id, render_result(profile), result_keyboard(session_id))
    await track_event(user_id, "result_shown", {"goal": profile.get("goal_code")}, db=db, session_id=session_id)
    await track_event(user_id, "quiz_finished", {"profile": profile}, db=db, session_id=session_id)


async def edit_course_menu(
    *,
    bot: Bot,
    chat_id: int,
    bot_message_id: int,
    course: dict[str, Any],
    notice: str | None = None,
) -> None:
    """Редактирует центральное сообщение в меню актуального курса."""

    modules = deserialize_course(course["route"])
    total_modules = len(modules) or int(course["total_modules"])
    current_module = int(course["current_module"])
    completed = course["status"] == "completed"
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_course_menu(
            course["profile"],
            course_id=int(course["id"]),
            current_module=current_module,
            total_modules=total_modules,
            completed=completed,
            notice=notice,
        ),
        course_menu_keyboard(
            course_id=int(course["id"]),
            current_module=current_module,
            total_modules=total_modules,
            completed=completed,
        ),
    )


async def edit_current_course_screen(
    *,
    bot: Bot,
    state: FSMContext,
    db: Database,
    user_id: int,
    notice: str,
) -> None:
    """Показывает notice в центральном меню текущего курса, не создавая новое сообщение."""

    data = await state.get_data()
    chat_id, bot_message_id = resolve_message_target(data)
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    if chat_id is None or bot_message_id is None or course_id is None:
        return

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != user_id:
        return

    await edit_course_menu(
        bot=bot,
        chat_id=chat_id,
        bot_message_id=bot_message_id,
        course=course,
        notice=notice,
    )


async def open_certificates_gallery(
    *,
    bot: Bot,
    state: FSMContext,
    db: Database,
    user_id: int,
    chat_id: int,
    old_message_id: int,
    certificates: list[dict[str, Any]],
    page: int,
    course_id: int | None,
) -> None:
    """Открывает просмотр сертификатов: для фото удаляет меню и отправляет галерею."""

    image_certificates = [certificate for certificate in certificates if _is_image_certificate(certificate)]
    if not image_certificates:
        await edit_quiz_message(
            bot,
            chat_id,
            old_message_id,
            render_certificates_list(certificates),
            certificates_menu_keyboard(course_id),
        )
        return

    await delete_gallery_messages(bot, chat_id, list((await state.get_data()).get("certificate_message_ids", [])))
    try:
        await bot.delete_message(chat_id=chat_id, message_id=old_message_id)
    except TelegramBadRequest as error:
        logger.info("Не удалось удалить центральное сообщение перед галереей: %s", error)

    await state.update_data(bot_message_id=None)
    await send_certificates_gallery(
        bot=bot,
        state=state,
        chat_id=chat_id,
        certificates=certificates,
        page=page,
        course_id=course_id,
    )


async def send_certificates_gallery(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    certificates: list[dict[str, Any]],
    page: int,
    course_id: int | None,
) -> None:
    """Отправляет страницу фотосертификатов и сохраняет id сообщений для последующего удаления."""

    image_certificates = [certificate for certificate in certificates if _is_image_certificate(certificate)]
    other_certificates = [certificate for certificate in certificates if not _is_image_certificate(certificate)]
    per_page = 5
    total_pages = max(1, (len(image_certificates) + per_page - 1) // per_page)
    current_page = min(max(page, 0), total_pages - 1)
    start = current_page * per_page
    page_items = image_certificates[start : start + per_page]

    sent_messages: list[Message] = []
    for index, certificate in enumerate(page_items, start=start + 1):
        is_last = index == start + len(page_items)
        caption = (
            f"📚 Сертификат {index}/{len(image_certificates)}\n"
            f"{escape(str(certificate['title']))}\n"
            f"Загружен: {escape(str(certificate['uploaded_at']))}"
        )
        if is_last and other_certificates:
            caption += f"\n\nЕще документов: {len(other_certificates)}"
        local_path = Path(str(certificate.get("local_path", "")))
        photo = FSInputFile(local_path) if local_path.is_file() else str(certificate["telegram_file_id"])
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=certificates_gallery_keyboard(current_page, total_pages) if is_last else None,
        )
        sent_messages.append(sent)

    if not sent_messages:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=render_certificates_list(certificates),
            reply_markup=certificates_gallery_keyboard(current_page, total_pages),
        )
        sent_messages.append(sent)

    await state.update_data(
        chat_id=chat_id,
        bot_message_id=sent_messages[-1].message_id,
        certificate_message_ids=[message.message_id for message in sent_messages],
        certificate_page=current_page,
        course_id=course_id,
    )


async def delete_gallery_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    """Удаляет сообщения галереи сертификатов."""

    for message_id in sorted(set(int(item) for item in message_ids if item)):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest as error:
            logger.info("Не удалось удалить сообщение галереи сертификатов: %s", error)


async def send_home_message(
    *,
    bot: Bot,
    state: FSMContext,
    db: Database,
    user_id: int,
    chat_id: int,
) -> None:
    """Восстанавливает центральное меню после галереи сертификатов."""

    data = await state.get_data()
    course_id = _parse_positive_int(str(data.get("course_id", "")))
    if course_id is not None:
        course = await db.get_course_session(course_id)
        if course is not None and int(course["telegram_user_id"]) == user_id:
            modules = deserialize_course(course["route"])
            total_modules = len(modules) or int(course["total_modules"])
            completed = course["status"] == "completed"
            message = await bot.send_message(
                chat_id=chat_id,
                text=render_course_menu(
                    course["profile"],
                    course_id=course_id,
                    current_module=int(course["current_module"]),
                    total_modules=total_modules,
                    completed=completed,
                ),
                reply_markup=course_menu_keyboard(
                    course_id=course_id,
                    current_module=int(course["current_module"]),
                    total_modules=total_modules,
                    completed=completed,
                ),
            )
            await state.update_data(
                chat_id=chat_id,
                bot_message_id=message.message_id,
                certificate_message_ids=[],
                profile=dict(course["profile"]),
            )
            return

    profile: dict[str, str] = dict(data.get("profile", {}))
    message = await bot.send_message(
        chat_id=chat_id,
        text=render_result(profile) if profile else render_intro(),
        reply_markup=result_keyboard(_parse_positive_int(str(data.get("session_id", "")))) if profile else start_keyboard(),
    )
    await state.update_data(chat_id=chat_id, bot_message_id=message.message_id, certificate_message_ids=[])


async def complete_course_module(
    *,
    bot: Bot,
    chat_id: int,
    bot_message_id: int,
    state: FSMContext,
    db: Database,
    user_id: int,
    course_id: int,
    module_index: int,
) -> None:
    """Общий переход между модулями курса для кнопки и текстовой команды."""

    course = await db.get_course_session(course_id)
    if course is None or int(course["telegram_user_id"]) != user_id:
        await edit_quiz_message(
            bot,
            chat_id,
            bot_message_id,
            "Не нашел этот маршрут. Запусти /restart, чтобы собрать новый.",
            start_keyboard(),
        )
        return
    if course["status"] == "completed":
        await edit_course_menu(
            bot=bot,
            chat_id=chat_id,
            bot_message_id=bot_message_id,
            course=course,
            notice="Этот маршрут уже завершен. Сертификат доступен из центрального меню.",
        )
        return

    current_module = int(course["current_module"])
    if module_index != current_module:
        await edit_course_menu(
            bot=bot,
            chat_id=chat_id,
            bot_message_id=bot_message_id,
            course=course,
            notice="Этот модуль уже не текущий. Открой актуальный шаг из центрального меню.",
        )
        return

    modules = deserialize_course(course["route"])
    if not modules or module_index >= len(modules):
        await edit_quiz_message(
            bot,
            chat_id,
            bot_message_id,
            "Маршрут поврежден или пустой. Запусти /restart, чтобы собрать новый.",
            start_keyboard(),
        )
        return

    await db.save_course_event(
        course_id=course_id,
        user_id=user_id,
        module_index=module_index,
        event_name="module_completed",
        payload={"module_title": modules[module_index].title},
    )

    next_index = module_index + 1
    if next_index < len(modules):
        await db.update_course_progress(course_id, next_index)
        updated_course = await db.get_course_session(course_id)
        await state.set_state(CourseState.in_progress)
        await state.update_data(
            course_id=course_id,
            current_module=next_index,
            course_total=len(modules),
            profile=dict(course["profile"]),
            chat_id=chat_id,
            bot_message_id=bot_message_id,
        )
        await edit_course_menu(
            bot=bot,
            chat_id=chat_id,
            bot_message_id=bot_message_id,
            course=updated_course or course,
            notice=f"✅ Модуль {module_index + 1} засчитан. Следующий модуль открыт в меню.",
        )
        return

    certificate_code = make_certificate_code(user_id, course_id)
    await db.complete_course_session(course_id, certificate_code)
    await db.save_course_event(
        course_id=course_id,
        user_id=user_id,
        module_index=module_index,
        event_name="course_completed",
        payload={"certificate_code": certificate_code},
    )
    await state.set_state(CourseState.completed)
    await state.update_data(
        course_id=course_id,
        current_module=len(modules),
        course_total=len(modules),
        certificate_code=certificate_code,
        profile=dict(course["profile"]),
        chat_id=chat_id,
        bot_message_id=bot_message_id,
    )
    await edit_quiz_message(
        bot,
        chat_id,
        bot_message_id,
        render_course_certificate(
            course["profile"],
            course_id=course_id,
            certificate_code=certificate_code,
            total_modules=len(modules),
        ),
        completed_course_keyboard(course_id),
    )


async def save_uploaded_certificate(message: Message, bot: Bot, db: Database) -> dict[str, Any]:
    """Скачивает файл сертификата из Telegram и сохраняет метаданные в SQLite."""

    user_id = message.from_user.id
    if message.document is not None:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        original_name = message.document.file_name or "certificate"
        file_type = message.document.mime_type or "document"
        suffix = Path(original_name).suffix or ".bin"
        title = (message.caption or Path(original_name).stem or "Сертификат").strip()[:120]
    else:
        photo = message.photo[-1]
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id
        file_type = "image/jpeg"
        suffix = ".jpg"
        title = (message.caption or "Сертификат").strip()[:120]

    if not title:
        title = "Сертификат"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{file_unique_id}{suffix}"
    relative_path = Path("certificates") / str(user_id) / safe_name
    local_path = Path("data") / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)

    await bot.download(file_id, destination=local_path)
    certificate_id = await db.save_certificate(
        user_id=user_id,
        title=title,
        file_type=file_type,
        telegram_file_id=file_id,
        telegram_file_unique_id=file_unique_id,
        local_path=str(local_path),
        source="telegram_upload",
    )
    await db.save_event(
        user_id=user_id,
        event_name="certificate_uploaded",
        payload={"certificate_id": certificate_id, "file_type": file_type, "title": title},
    )
    return {"id": certificate_id, "title": title, "file_type": file_type, "local_path": str(local_path)}


async def build_question(index: int, profile: dict[str, str], db: Database) -> QuizQuestion:
    """Строит вопрос, подмешивая динамический TOP-10 из запросов пользователей."""

    question = get_question(index, profile)
    if index != 1:
        return question

    goal_code = profile.get("goal_code", "skill")
    dynamic_options = await build_dynamic_top10_options(db, goal_code)
    return replace_question_options(question, dynamic_options)


async def build_dynamic_top10_options(db: Database, goal_code: str) -> tuple[QuizOption, ...]:
    """Формирует TOP-10: сначала реальные запросы пользователей, затем seed для холодного старта."""

    popular_rows = await db.get_top_interest_answers(goal_code, limit=10)
    options: list[QuizOption] = [
        QuizOption(
            code=row["code"],
            label=row["label"],
            profile_value=row["value"],
            tone=row["tone"],
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


def resolve_message_target(data: dict[str, Any], message: Message | None = None) -> tuple[int | None, int | None]:
    """Берет id чата и сообщения бота из FSM, а при необходимости из callback-сообщения."""

    chat_id = data.get("chat_id")
    bot_message_id = data.get("bot_message_id")

    if chat_id is None and message is not None:
        chat_id = message.chat.id
    if bot_message_id is None and message is not None:
        bot_message_id = message.message_id

    return chat_id, bot_message_id


async def edit_quiz_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    """Редактирует одно сообщение бота и спокойно игнорирует повторный одинаковый текст."""

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            return
        raise


async def delete_user_message(
    bot: Bot,
    message: Message,
    db: Database,
    session_id: int | None,
) -> None:
    """Удаляет учтенное текстовое сообщение пользователя, чтобы чат оставался чистым."""

    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramBadRequest as error:
        logger.info("Не удалось удалить сообщение пользователя: %s", error)
        await track_event(
            message.from_user.id,
            "user_message_delete_failed",
            {"message_id": message.message_id, "error": str(error)},
            db=db,
            session_id=session_id,
        )


def _parse_positive_int(raw_value: str) -> int | None:
    """Парсит положительный id из callback_data."""

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_non_negative_int(raw_value: str) -> int | None:
    """Парсит индекс модуля из callback_data."""

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _is_image_certificate(certificate: dict[str, Any]) -> bool:
    """Проверяет, можно ли показать сертификат как фото в Telegram."""

    return str(certificate.get("file_type", "")).casefold().startswith("image/")
