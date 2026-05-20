"""Формирование текстов и inline-клавиатур для экранов теста."""

from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.course import CourseModule, recommended_specialties, render_qr_placeholder
from bot.quiz import TOTAL_STEPS, QuizQuestion, get_result


def progress_bar(step_index: int) -> str:
    """Рисует компактный прогресс прямо в сообщении."""

    filled = "●" * step_index
    empty = "○" * (TOTAL_STEPS - step_index)
    percent = round(step_index / TOTAL_STEPS * 100)
    return f"{filled}{empty} · {percent}%"


def start_keyboard() -> InlineKeyboardMarkup:
    """Кнопка старта превращает обычный `/start` в осознанное начало маршрута."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Собрать мой маршрут", callback_data="quiz:start")],
        ]
    )


def question_keyboard(
    question: QuizQuestion,
    index: int,
    selected_codes: list[str] | None = None,
    *,
    can_go_back: bool = False,
    draft_messages: list[str] | None = None,
) -> InlineKeyboardMarkup:
    """Создает inline-кнопки по две в ряд и служебные кнопки навигации."""

    selected = set(selected_codes or [])
    draft = draft_messages or []
    buttons: list[InlineKeyboardButton] = []
    for option in question.options:
        text = f"✅ {option.label}" if question.multi_select and option.code in selected else option.label
        callback_prefix = "quiz:toggle" if question.multi_select else "quiz:answer"
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{callback_prefix}:{index}:{option.code}",
            )
        )

    columns = 1 if question.profile_key == "level" else max(1, question.keyboard_columns)
    rows = [buttons[position : position + columns] for position in range(0, len(buttons), columns)]
    if draft:
        rows.append(
            [
                InlineKeyboardButton(text="Очистить свои варианты", callback_data=f"quiz:text_clear:{index}"),
            ]
        )

    if question.multi_select:
        control_row = []
        if can_go_back:
            control_row.append(InlineKeyboardButton(text="← Назад", callback_data=f"quiz:back:{index}"))
        control_row.append(InlineKeyboardButton(text="Готово", callback_data=f"quiz:done:{index}"))
        rows.append(control_row)
    elif can_go_back:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=f"quiz:back:{index}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def restart_keyboard() -> InlineKeyboardMarkup:
    """Дает пользователю быстрый перезапуск без поиска команды в чате."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↻ Собрать заново", callback_data="quiz:start")],
        ]
    )


def result_keyboard(session_id: int | None = None) -> InlineKeyboardMarkup:
    """Клавиатура центрального меню сразу после онбординга."""

    return course_menu_keyboard(quiz_session_id=session_id)


def course_menu_keyboard(
    *,
    quiz_session_id: int | None = None,
    course_id: int | None = None,
    current_module: int = 0,
    total_modules: int = 4,
    completed: bool = False,
) -> InlineKeyboardMarkup:
    """Центральное меню курса: все разделы открываются через редактирование сообщения."""

    rows: list[list[InlineKeyboardButton]] = []
    if course_id is None:
        course_session = quiz_session_id if quiz_session_id is not None else 0
        rows.append(
            [InlineKeyboardButton(text="▶️ Начать прохождение курса", callback_data=f"course:start:{course_session}")]
        )
    elif completed:
        rows.append([InlineKeyboardButton(text="🏆 Сертификат курса", callback_data=f"course:certificate:{course_id}")])
    else:
        module_number = min(current_module + 1, total_modules)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🧭 Открыть модуль {module_number}",
                    callback_data=f"course:module:{course_id}:{current_module}",
                )
            ]
        )

    rows.extend(
        [
            [InlineKeyboardButton(text="📚 Сертификаты", callback_data="certificates:menu")],
            [InlineKeyboardButton(text="↻ Собрать заново", callback_data="quiz:start")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_module_keyboard(course_id: int, module_index: int) -> InlineKeyboardMarkup:
    """Кнопки под текущим модулем: фидбек и отметка прохождения."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Полезно", callback_data=f"course:feedback:{course_id}:{module_index}:useful"),
                InlineKeyboardButton(text="🧱 Сложно", callback_data=f"course:feedback:{course_id}:{module_index}:hard"),
            ],
            [
                InlineKeyboardButton(text="🪶 Слишком просто", callback_data=f"course:feedback:{course_id}:{module_index}:easy"),
                InlineKeyboardButton(text="🔁 Не подошло", callback_data=f"course:feedback:{course_id}:{module_index}:bad_fit"),
            ],
            [InlineKeyboardButton(text="✅ Модуль пройден", callback_data=f"course:complete:{course_id}:{module_index}")],
            [InlineKeyboardButton(text="📚 Сертификаты", callback_data="certificates:menu")],
            [InlineKeyboardButton(text="← В центральное меню", callback_data=f"course:menu:{course_id}")],
        ]
    )


def completed_course_keyboard(course_id: int) -> InlineKeyboardMarkup:
    """Кнопки после выдачи достижения и сертификата."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← В центральное меню", callback_data=f"course:menu:{course_id}")],
            [InlineKeyboardButton(text="📚 Сертификаты", callback_data="certificates:menu")],
            [InlineKeyboardButton(text="↻ Собрать новый маршрут", callback_data="quiz:start")],
        ]
    )


def certificates_keyboard(course_id: int | None = None) -> InlineKeyboardMarkup:
    """Клавиатура экранов сертификатов с возвратом в центральное меню."""

    rows: list[list[InlineKeyboardButton]] = []
    if course_id is not None:
        rows.append([InlineKeyboardButton(text="← В центральное меню", callback_data=f"course:menu:{course_id}")])
    else:
        rows.append([InlineKeyboardButton(text="← В центральное меню", callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text="↻ Собрать новый маршрут", callback_data="quiz:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def certificates_menu_keyboard(course_id: int | None = None) -> InlineKeyboardMarkup:
    """Меню сертификатов: просмотр и загрузка внутри одного раздела."""

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="📚 Мои сертификаты", callback_data="certificates:list:0")],
        [InlineKeyboardButton(text="📎 Загрузить сертификат", callback_data="certificates:upload")],
    ]
    if course_id is not None:
        rows.append([InlineKeyboardButton(text="← В центральное меню", callback_data=f"course:menu:{course_id}")])
    else:
        rows.append([InlineKeyboardButton(text="← В центральное меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def certificates_gallery_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Навигация по галерее сертификатов."""

    rows: list[list[InlineKeyboardButton]] = []
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="← Назад", callback_data=f"certificates:page:{page - 1}"))
    if page + 1 < total_pages:
        nav_row.append(InlineKeyboardButton(text="Дальше →", callback_data=f"certificates:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="← В центральное меню", callback_data="certificates:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_intro() -> str:
    """Первый экран обещает быстрый персональный результат вместо длинной анкеты."""

    return (
        "✨ <b>Соберем личный маршрут обучения</b>\n\n"
        "Ответь на 7 коротких вопросов. Можно нажимать кнопки или писать свой вариант с клавиатуры. "
        "Навык или специальность могут быть любыми: программирование, дизайн, маркетинг, кулинария, ветеринария или твой вариант. "
        "В конце появится маршрут: с чего начать, как учиться и что делать дальше.\n\n"
        f"<b>Прогресс:</b> {progress_bar(0)}\n"
        "Начнем?"
    )


def render_question(
    question: QuizQuestion,
    index: int,
    selected_codes: list[str] | None = None,
    draft_messages: list[str] | None = None,
) -> str:
    """Рендерит экран вопроса с мотивационным прогрессом."""

    step = index + 1
    support = "Подбираем подходящий вариант" if step < TOTAL_STEPS else "Почти готово"
    draft = draft_messages or []
    if question.multi_select:
        selected_count = len(selected_codes or [])
        manual_hint = f"\n\nМожно выбрать несколько вариантов или написать свой. Выбрано: {selected_count}."
    else:
        manual_hint = "\n\nВыбери кнопку или напиши свой вариант."

    draft_text = ""
    if draft:
        escaped_draft = escape("\n".join(draft))
        draft_text = f"\n\n<b>Свои варианты:</b>\n{escaped_draft}"

    return (
        f"<b>{question.title}</b>\n"
        f"{question.subtitle}"
        f"{manual_hint if question.allow_manual else ''}\n\n"
        f"<b>Шаг {step}/{TOTAL_STEPS}</b> · {support}\n"
        f"<b>Прогресс:</b> {progress_bar(index)}"
        f"{draft_text}"
    )


def render_building(message: str) -> str:
    """Показывает промежуточный экран обработки после последнего ответа."""

    return (
        "🪄 <b>Строю персональный маршрут</b>\n\n"
        f"{message}\n\n"
        f"<b>Прогресс:</b> {progress_bar(TOTAL_STEPS)}"
    )


def render_result(profile: dict[str, str]) -> str:
    """Собирает центральное меню после онбординга с готовностью начать курс."""

    result = get_result(profile)

    specialties_text = ""
    if profile.get("goal_code") == "explore":
        specialties = ", ".join(recommended_specialties(profile)[:5])
        specialties_text = f"\n<b>Варианты:</b> {escape(specialties)}\n"

    return (
        f"🏁 <b>{escape(str(result['hero']))}</b>\n\n"
        f"<b>Направление:</b> {_profile_value(profile, 'interest')}\n"
        f"<b>Ближайший результат:</b> {_profile_value(profile, 'focus')}\n"
        f"<b>Темп:</b> {_profile_value(profile, 'time')}\n"
        f"{specialties_text}\n"
        f"{escape(str(result['how_to_use']))}"
    )


def render_course_menu(
    profile: dict[str, str],
    *,
    course_id: int | None,
    current_module: int = 0,
    total_modules: int = 4,
    completed: bool = False,
    notice: str | None = None,
) -> str:
    """Рендерит центральное меню курса в одном редактируемом сообщении."""

    completed_modules = total_modules if completed else min(current_module, total_modules)
    progress = _course_progress_bar(completed_modules, total_modules)
    status = "маршрут завершен" if completed else f"текущий модуль: {min(current_module + 1, total_modules)}"
    notice_text = f"{escape(notice)}\n\n" if notice else ""
    return (
        f"{notice_text}"
        "🧭 <b>Центральное меню маршрута</b>\n\n"
        f"<b>Тема:</b> {_profile_value(profile, 'interest')}\n"
        f"<b>Цель:</b> {_profile_value(profile, 'goal')}\n"
        f"<b>Статус:</b> {escape(status)}\n"
        f"<b>Прогресс:</b> {progress}\n\n"
        "Открывай текущий модуль из меню. Из модуля можно вернуться сюда без новых сообщений."
    )


def render_course_module(module: CourseModule, module_index: int, total_modules: int) -> str:
    """Красиво оформляет один модуль курса в Telegram-сообщении."""

    materials = "\n".join(
        (
            f"{position}. <b>{escape(material.kind)}:</b> {escape(material.title)}\n"
            f"   Источник: {escape(material.source)}\n"
            f"   Время: {escape(material.duration)}\n"
            f"   Как работать: {escape(material.interaction)}"
        )
        for position, material in enumerate(module.materials, start=1)
    )
    skills = ", ".join(escape(skill) for skill in module.skills)

    return (
        f"🧭 <b>{escape(module.title)}</b>\n"
        f"<b>Шаг {module_index + 1}/{total_modules}</b> · {escape(module.duration)}\n\n"
        f"{escape(module.description)}\n\n"
        f"<b>Результат модуля:</b>\n{escape(module.outcome)}\n\n"
        f"<b>Материалы:</b>\n{materials}\n\n"
        f"<b>Практика:</b>\n{escape(module.practice)}\n\n"
        f"<b>Развиваемые навыки:</b> {skills}\n"
        f"<b>Связь с возможностями:</b> {escape(module.career_link)}"
    )


def render_course_feedback_ack(feedback_code: str) -> str:
    """Отвечает на фидбек по материалу без перестройки маршрута в текущем прототипе."""

    messages = {
        "useful": "Отметил: материал полезен. Такой формат можно чаще использовать дальше.",
        "hard": "Отметил: слишком сложно. В следующей итерации здесь будет замена на более мягкий материал.",
        "easy": "Отметил: слишком просто. В следующей итерации здесь будет более продвинутый вариант.",
        "bad_fit": "Отметил: не подошло. В следующей итерации бот будет заменять материал по формату.",
    }
    return messages.get(feedback_code, "Фидбек сохранен.")


def render_course_certificate(
    profile: dict[str, str],
    *,
    course_id: int,
    certificate_code: str,
    total_modules: int,
) -> str:
    """Финальный экран достижения и сертификата в стиле приложения Прогрессоры."""

    qr = render_qr_placeholder(certificate_code)
    return (
        "🏆 <b>Достижение разблокировано: Маршрут пройден</b>\n\n"
        "Сертификат подтверждает прохождение курса в прототипе «Прогрессоры».\n\n"
        "<b>Сертификат</b>\n"
        f"Направление: {_profile_value(profile, 'interest')}\n"
        f"Курс: персональный маршрут обучения\n"
        f"Модулей пройдено: {total_modules}/{total_modules}\n"
        f"Код подтверждения: <code>{escape(certificate_code)}</code>\n"
        f"ID маршрута: <code>{course_id}</code>\n\n"
        "<b>QR-подтверждение:</b>\n"
        f"<pre>{qr}</pre>\n\n"
        "Теперь можно загрузить внешние сертификаты: PDF, изображение или файл. "
        "Я сохраню их в боте и покажу в списке сертификатов."
    )


def render_certificates_help() -> str:
    """Инструкция по загрузке сертификатов."""

    return (
        "📎 <b>Загрузка сертификатов</b>\n\n"
        "Отправь сюда PDF, изображение или другой файл сертификата. "
        "Можно добавить подпись к файлу — она станет названием сертификата.\n\n"
        "После загрузки файл сохранится в хранилище бота."
    )


def render_certificates_menu(certificates_count: int) -> str:
    """Главный экран раздела сертификатов."""

    return (
        "📚 <b>Сертификаты</b>\n\n"
        f"Сохранено: <b>{certificates_count}</b>\n\n"
        "Можно посмотреть загруженные сертификаты или добавить новый файл."
    )


def render_certificate_saved(saved: dict[str, str], certificates: list[dict[str, str]]) -> str:
    """Показывает подтверждение загрузки и текущий список сертификатов."""

    return (
        "✅ <b>Сертификат сохранен</b>\n\n"
        f"Название: <b>{escape(str(saved['title']))}</b>\n"
        f"Тип: {escape(str(saved['file_type']))}\n"
        f"ID в хранилище: <code>{escape(str(saved['id']))}</code>\n\n"
        f"{render_certificates_list(certificates)}"
    )


def render_certificates_list(certificates: list[dict[str, str]]) -> str:
    """Показывает список загруженных сертификатов пользователя."""

    if not certificates:
        return (
            "📚 <b>Мои сертификаты</b>\n\n"
            "Пока сертификатов нет. Отправь PDF, изображение или файл сертификата в чат, и я сохраню его."
        )

    rows = []
    for certificate in certificates:
        rows.append(
            f"• <b>{escape(str(certificate['title']))}</b>\n"
            f"  Тип: {escape(str(certificate['file_type']))} · Загружен: {escape(str(certificate['uploaded_at']))}"
        )

    return "📚 <b>Мои сертификаты</b>\n\n" + "\n\n".join(rows)


def _profile_value(profile: dict[str, str], key: str) -> str:
    """Безопасно выводит значение профиля в HTML-сообщении Telegram."""

    return escape(profile.get(key, "не указано"))


def _course_progress_bar(completed_modules: int, total_modules: int) -> str:
    """Рисует прогресс прохождения модулей."""

    total = max(total_modules, 1)
    completed = min(max(completed_modules, 0), total)
    filled = "●" * completed
    empty = "○" * (total - completed)
    percent = round(completed / total * 100)
    return f"{filled}{empty} · {percent}%"
