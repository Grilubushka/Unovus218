from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape


TOTAL_STEPS = 7


@dataclass(frozen=True)
class QuizOption:
    code: str
    label: str
    profile_value: str
    tone: str


@dataclass(frozen=True)
class QuizQuestion:
    code: str
    title: str
    subtitle: str
    profile_key: str
    options: tuple[QuizOption, ...]
    allow_manual: bool = True
    multi_select: bool = False
    keyboard_columns: int = 2


def empty_session() -> dict:
    return {
        "step": 0,
        "profile": {},
        "selected_options": [],
        "draft_messages": [],
        "history": [],
        "presentation_cache": {},
    }


def current_question(session: dict) -> QuizQuestion | None:
    step = int(session.get("step", 0))
    if step >= TOTAL_STEPS:
        return None
    return get_question(step, dict(session.get("profile", {})))


def get_question(index: int, profile: dict[str, str] | None = None) -> QuizQuestion:
    profile = profile or {}
    if index == 0:
        return _goal_question()
    if index == 1:
        return _interest_question(profile)
    if index == 2:
        return _age_question()
    if index == 3:
        return _focus_question(profile)
    if index == 4:
        return _level_question(profile)
    if index == 5:
        return _time_question(profile)
    if index == 6:
        return _constraint_question(profile)
    raise IndexError(f"Нет вопроса с индексом {index}.")


def get_option(question: QuizQuestion, option_code: str) -> QuizOption | None:
    return next((option for option in question.options if option.code == option_code), None)


def replace_question_options(question: QuizQuestion, options: tuple[QuizOption, ...]) -> QuizQuestion:
    return replace(question, options=options)


def create_manual_option(question: QuizQuestion, raw_text: str) -> QuizOption:
    cleaned = " ".join(raw_text.strip().split())[:120]
    if not cleaned:
        cleaned = "свой вариант"

    value_by_key = {
        "goal": f"цель пользователя: {cleaned}",
        "interest": f"навык или специальность пользователя: {cleaned}",
        "age": f"возраст пользователя: {cleaned}",
        "focus": f"ожидаемый результат: {cleaned}",
        "level": f"опыт и текущие навыки пользователя: {cleaned}",
        "time": f"готов выделять на обучение: {cleaned}",
        "constraints": f"важное ограничение: {cleaned}",
    }

    return QuizOption(
        code="custom",
        label=cleaned,
        profile_value=value_by_key.get(question.profile_key, cleaned),
        tone="ручной ввод",
    )


def create_multi_option(question: QuizQuestion, options: list[QuizOption]) -> QuizOption:
    return QuizOption(
        code=",".join(option.code for option in options),
        label=", ".join(option.label for option in options),
        profile_value="; ".join(option.profile_value for option in options),
        tone=", ".join(option.tone for option in options),
    )


def apply_answer(session: dict, question: QuizQuestion, option: QuizOption) -> bool:
    current_step = int(session.get("step", 0))
    profile: dict[str, str] = dict(session.get("profile", {}))
    history: list[dict] = list(session.get("history", []))
    history.append({"step": current_step, "profile": dict(profile)})

    profile[question.profile_key] = option.profile_value
    profile[f"{question.profile_key}_code"] = option.code
    profile[f"{question.profile_key}_tone"] = option.tone

    next_step = current_step + 1
    session["step"] = next_step
    session["profile"] = profile
    session["selected_options"] = []
    session["draft_messages"] = []
    session["history"] = history
    return next_step >= TOTAL_STEPS


def go_back(session: dict) -> bool:
    history: list[dict] = list(session.get("history", []))
    if not history:
        return False

    previous = history.pop()
    session["step"] = int(previous.get("step", 0))
    session["profile"] = dict(previous.get("profile", {}))
    session["selected_options"] = []
    session["draft_messages"] = []
    session["history"] = history
    return True


def progress_bar(step_index: int) -> str:
    filled = "●" * step_index
    empty = "○" * (TOTAL_STEPS - step_index)
    percent = round(step_index / TOTAL_STEPS * 100)
    return f"{filled}{empty} · {percent}%"


def render_intro() -> str:
    return (
        "✨ <b>Соберем личный маршрут обучения</b>\n\n"
        "Ответь на 7 коротких вопросов. Можно нажимать кнопки или писать свой вариант с клавиатуры. "
        "Навык или специальность могут быть любыми: программирование, дизайн, маркетинг, кулинария, "
        "ветеринария или твой вариант.\n\n"
        "После онбординга я передам тебя в Mini App, где откроется работа с маршрутом.\n\n"
        f"<b>Прогресс:</b> {progress_bar(0)}\n"
        "Начнем?"
    )


def render_question(
    question: QuizQuestion,
    index: int,
    selected_codes: list[str] | None = None,
    draft_messages: list[str] | None = None,
    copy: dict[str, str] | None = None,
) -> str:
    step = index + 1
    copy = copy or {}
    title = copy.get("title") or question.title
    subtitle = copy.get("subtitle") or question.subtitle
    support = copy.get("support") or ("Подбираем подходящий вариант" if step < TOTAL_STEPS else "Почти готово")
    draft = draft_messages or []
    if question.multi_select:
        selected_count = len(selected_codes or [])
        default_manual_hint = f"Можно выбрать несколько вариантов или написать свой. Выбрано: {selected_count}."
    else:
        default_manual_hint = "Выбери кнопку или напиши свой вариант."

    manual_hint = copy.get("manual_hint") or default_manual_hint

    draft_text = ""
    if draft:
        escaped_draft = escape("\n".join(draft))
        draft_text = f"\n\n<b>Свои варианты:</b>\n{escaped_draft}"

    manual_hint_text = f"\n\n{escape(manual_hint)}" if question.allow_manual and manual_hint else ""

    return (
        f"<b>{escape(title)}</b>\n"
        f"{escape(subtitle)}"
        f"{manual_hint_text}\n\n"
        f"<b>Шаг {step}/{TOTAL_STEPS}</b> · {escape(support)}\n"
        f"<b>Прогресс:</b> {progress_bar(index)}"
        f"{draft_text}"
    )


def render_completion(profile: dict[str, str], copy: dict | None = None) -> str:
    result = get_result(profile)
    specialties_text = ""
    if profile.get("goal_code") == "explore":
        specialties = ", ".join(recommended_specialties(profile)[:5])
        specialties_text = f"\n• <b>Варианты:</b> {escape(specialties)}"

    copy = copy or {}
    headline = copy.get("headline") or "Маршрут готов"
    lead = copy.get("lead") or "Я собрал короткий портрет, чтобы Mini App открыл маршрут без лишнего шума и с понятным первым шагом."
    highlights = copy.get("highlights") or [
        {"label": "Направление", "value": _profile_value_raw(profile, "interest", "direction")},
        {"label": "Результат", "value": _profile_value_raw(profile, "focus", "result")},
        {"label": "Темп", "value": _profile_value_raw(profile, "time", "weekly_time", "weeklyTime")},
        {"label": "Уровень", "value": _profile_value_raw(profile, "level")},
    ]
    next_step = copy.get("next_step") or "Открой Mini App и начни с первого модуля: там будет стартовая диагностика и ближайшее действие."
    tone_note = copy.get("tone_note") or result["how_to_use"]

    highlight_lines = []
    for item in highlights[:5]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if label and value:
            highlight_lines.append(f"• <b>{escape(label)}:</b> {escape(value)}")
    highlights_text = "\n".join(highlight_lines)

    return (
        f"✅ <b>{escape(str(headline))}</b>\n\n"
        f"🏁 <b>{escape(str(result['hero']))}</b>\n"
        f"{escape(str(lead))}\n\n"
        "📌 <b>Портрет маршрута</b>\n"
        f"{highlights_text}"
        f"{specialties_text}\n\n"
        f"🧭 <b>Как двигаться:</b> {escape(str(tone_note))}\n"
        f"🎯 <b>Следующий шаг:</b> {escape(str(next_step))}\n\n"
        "Профиль сохранен. Дальше маршрут, прогресс и материалы открываются в Mini App."
    )


def get_result(profile: dict[str, str]) -> dict[str, str]:
    goal_code = profile.get("goal_code", "skill")
    time_code = profile.get("time_code", "balanced")
    constraint_codes = set(profile.get("constraints_code", "custom").split(","))

    base = _base_result(goal_code)
    hero = _hero_name(base["hero"], time_code, constraint_codes)
    return {"hero": hero, "how_to_use": _how_to_use(time_code, goal_code)}


def recommended_specialties(profile: dict[str, str]) -> list[str]:
    interest_code = profile.get("interest_code", "")
    if interest_code == "creative_tech":
        return ["UX/UI дизайнер", "контент-дизайнер", "моушн-дизайнер", "frontend-разработчик", "продакт-дизайнер"]
    if interest_code == "analytics_logic":
        return ["аналитик данных", "BI-аналитик", "тестировщик", "финансовый аналитик", "AI-инженер"]
    if interest_code == "people_communication":
        return ["преподаватель", "HR-специалист", "менеджер поддержки", "sales-менеджер", "community manager"]
    if interest_code == "business_media":
        return ["digital-маркетолог", "SMM-специалист", "project manager", "продюсер", "контент-менеджер"]
    if interest_code == "health_nature":
        return ["ветеринарный ассистент", "лаборант", "медицинский регистратор", "экологический волонтер", "кинолог"]
    if interest_code == "hands_on":
        return ["повар-кондитер", "электромонтажник", "мастер сервиса", "оператор станка", "техник"]
    return ["AI-инженер", "аналитик данных", "UX/UI дизайнер", "digital-маркетолог", "project manager"]


def _goal_question() -> QuizQuestion:
    return QuizQuestion(
        code="goal",
        title="Куда ведем маршрут?",
        subtitle="Выбери главную цель. От нее зависят следующие вопросы и первый маршрут.",
        profile_key="goal",
        options=(
            QuizOption("career", "🚀 В карьеру", "хочет быстрее выйти на карьерный результат", "карьерный рывок"),
            QuizOption("skill", "🧠 Освоить навык", "хочет освоить конкретный навык с понятным результатом", "точечный апгрейд"),
            QuizOption("exam", "🎓 Учеба / экзамен", "учится ради учебной цели, проекта или экзамена", "учебный фокус"),
            QuizOption("explore", "🤔 Не знаю, что выбрать", "хочет подобрать несколько подходящих направлений", "поиск направления"),
        ),
    )


def _interest_question(profile: dict[str, str]) -> QuizQuestion:
    goal_code = profile.get("goal_code", "skill")
    title_by_goal = {
        "career": "Выбери специальность из TOP-10",
        "exam": "Выбери учебный трек из TOP-10",
        "explore": "Что тебе ближе?",
        "skill": "Выбери навык из TOP-10",
    }
    subtitle_by_goal = {
        "career": "Это популярные направления прямо сейчас. Если твоей специальности нет, просто напиши ее сообщением.",
        "exam": "Это частые учебные и проектные треки. Если нужного нет, просто напиши свой вариант.",
        "explore": "Выбери интересы, а дальше Mini App предложит направления, которые стоит попробовать.",
        "skill": "Это популярные навыки для самообучения прямо сейчас. Если нужного нет, просто напиши его сообщением.",
    }

    return QuizQuestion(
        code="interest",
        title=title_by_goal.get(goal_code, title_by_goal["skill"]),
        subtitle=subtitle_by_goal.get(goal_code, subtitle_by_goal["skill"]),
        profile_key="interest",
        options=seed_top10_options(goal_code),
    )


def seed_top10_options(goal_code: str) -> tuple[QuizOption, ...]:
    if goal_code == "career":
        return (
            QuizOption("ai_engineer", "🤖 AI-инженер", "интересуется специальностью AI-инженер", "цифровой трек"),
            QuizOption("data_analyst", "📊 Data analyst", "интересуется специальностью аналитик данных", "аналитический трек"),
            QuizOption("cybersecurity", "🛡 Кибербезопасность", "интересуется специальностью в кибербезопасности", "цифровой трек"),
            QuizOption("web_developer", "💻 Web/Python dev", "интересуется специальностью веб- или Python-разработчик", "цифровой трек"),
            QuizOption("ux_ui_designer", "🎨 UX/UI дизайнер", "интересуется специальностью UX/UI-дизайнер", "креативный трек"),
            QuizOption("digital_marketer", "📈 Digital-маркетолог", "интересуется специальностью digital-маркетолог", "проектный трек"),
            QuizOption("project_manager", "🧭 Project manager", "интересуется специальностью project manager", "проектный трек"),
            QuizOption("healthcare_vet_assistant", "🩺 Вет/мед ассистент", "интересуется медицинской или ветеринарной ассистентской ролью", "трек заботы"),
            QuizOption("chef_pastry", "🍳 Повар-кондитер", "интересуется специальностью повар или кондитер", "практический трек"),
            QuizOption("solar_electrician", "⚡ Электромонтажник", "интересуется электромонтажом, энергетикой или прикладной технической ролью", "практический трек"),
        )

    if goal_code == "exam":
        return (
            QuizOption("math_exam", "🧮 Математика", "выбирает подготовку по математике", "исследовательский трек"),
            QuizOption("programming_exam", "💻 Программирование", "выбирает подготовку по программированию или информатике", "цифровой трек"),
            QuizOption("english_exam", "🗣 Английский", "выбирает подготовку по английскому языку", "языковой трек"),
            QuizOption("biology_vet", "🩺 Биология/вет", "выбирает биологию, медицину, ветеринарию или животных", "трек заботы"),
            QuizOption("chemistry", "🧪 Химия", "выбирает подготовку по химии", "исследовательский трек"),
            QuizOption("russian_writing", "✍️ Письмо/русский", "выбирает письмо, русский язык или эссе", "языковой трек"),
            QuizOption("social_economics", "📈 Общество/экономика", "выбирает обществознание, экономику или бизнес-темы", "проектный трек"),
            QuizOption("design_portfolio", "🎨 Портфолио дизайна", "выбирает творческое портфолио или дизайн-проект", "креативный трек"),
            QuizOption("research_project", "🔬 Исследование", "выбирает исследовательский проект, конкурс или олимпиаду", "исследовательский трек"),
            QuizOption("study_planning", "🧭 План подготовки", "выбирает систему подготовки, расписание и самодисциплину", "трек самоорганизации"),
        )

    if goal_code == "explore":
        return (
            QuizOption("creative_tech", "🎨 Креатив и технологии", "интересуются креативом, цифровыми продуктами и визуальными задачами", "креативно-цифровой трек"),
            QuizOption("analytics_logic", "📊 Логика и данные", "интересуются аналитикой, числами и поиском закономерностей", "аналитический трек"),
            QuizOption("people_communication", "🗣 Люди и коммуникация", "интересуются общением, обучением, продажами и командной работой", "коммуникационный трек"),
            QuizOption("business_media", "📈 Бизнес и медиа", "интересуются продвижением, контентом, проектами и рынками", "проектный трек"),
            QuizOption("health_nature", "🩺 Здоровье и природа", "интересуются заботой, медициной, биологией, животными или экологией", "трек заботы"),
            QuizOption("hands_on", "🛠 Практика руками", "интересуются прикладными задачами, сервисом, техникой или ремеслом", "практический трек"),
        )

    return (
        QuizOption("ai_tools", "🤖 AI-инструменты", "хочет освоить AI-инструменты и промптинг", "цифровой трек"),
        QuizOption("python", "💻 Python", "хочет освоить Python", "цифровой трек"),
        QuizOption("data_excel_sql", "📊 Excel/SQL аналитика", "хочет освоить аналитику в Excel, SQL и данных", "аналитический трек"),
        QuizOption("figma_design", "🎨 Figma/UI-дизайн", "хочет освоить Figma и UI-дизайн", "креативный трек"),
        QuizOption("video_content", "🎬 Видео/контент", "хочет освоить создание видео и контента", "креативный трек"),
        QuizOption("marketing_ads", "📈 Реклама/SMM", "хочет освоить рекламу, SMM и digital-маркетинг", "проектный трек"),
        QuizOption("english_speaking", "🗣 Английский разговор", "хочет освоить разговорный английский", "коммуникационный трек"),
        QuizOption("cooking_basics", "🍳 Кулинария", "хочет освоить кулинарию, выпечку или базовые техники кухни", "практический трек"),
        QuizOption("animal_care", "🐾 Уход за животными", "хочет освоить уход за животными или основы ветеринарной заботы", "трек заботы"),
        QuizOption("project_management", "🧭 Управление проектами", "хочет освоить управление проектами и командную работу", "проектный трек"),
    )


def _age_question() -> QuizQuestion:
    return QuizQuestion(
        code="age",
        title="Сколько тебе лет?",
        subtitle="Возраст нужен, чтобы не предлагать взрослый карьерный трек школьнику и наоборот.",
        profile_key="age",
        options=(
            QuizOption("14_17", "🧑‍🎓 14-17", "возраст 14-17 лет", "школьный контекст"),
            QuizOption("18_22", "🎒 18-22", "возраст 18-22 года", "студенческий контекст"),
            QuizOption("23_30", "💼 23-30", "возраст 23-30 лет", "ранний профессиональный контекст"),
            QuizOption("30_plus", "🧩 30+", "возраст 30+ лет", "профессиональный переход"),
        ),
    )


def _focus_question(profile: dict[str, str]) -> QuizQuestion:
    goal_code = profile.get("goal_code")
    if goal_code == "career":
        return QuizQuestion(
            code="career_focus",
            title="Что нужно получить первым?",
            subtitle="Выбери ближайший результат, под который Mini App соберет первые шаги.",
            profile_key="focus",
            options=(
                QuizOption("understand_role", "Понять профессию", "хочет понять задачи, требования и вход в профессию", "ориентация в роли"),
                QuizOption("base_skills", "Собрать базовые навыки", "хочет собрать базовые навыки для старта", "база для старта"),
                QuizOption("first_project", "Сделать учебный проект", "хочет сделать первый проект для портфолио", "проектный результат"),
                QuizOption("prepare_applications", "Подготовиться к откликам", "хочет подготовить резюме, портфолио или тестовое задание", "готовность к откликам"),
            ),
        )

    if goal_code == "exam":
        return QuizQuestion(
            code="study_focus",
            title="Что важнее в учебе?",
            subtitle="Выбери результат, который нужен в ближайшее время.",
            profile_key="focus",
            options=(
                QuizOption("close_gaps", "Закрыть пробелы", "хочет закрыть пробелы в базовых темах", "закрытие пробелов"),
                QuizOption("repeat_system", "Повторить по системе", "хочет повторять темы по понятному плану", "системное повторение"),
                QuizOption("solve_tasks", "Научиться решать задания", "хочет больше практики и самопроверки", "практика заданий"),
                QuizOption("study_project", "Сделать проект", "хочет подготовить учебный проект или работу", "учебный проект"),
            ),
        )

    if goal_code == "explore":
        return QuizQuestion(
            code="explore_focus",
            title="Как будем выбирать направление?",
            subtitle="Выбери формат, который поможет быстрее понять, что подходит.",
            profile_key="focus",
            options=(
                QuizOption("shortlist", "Получить список профессий", "хочет получить короткий список подходящих специальностей", "подбор профессий"),
                QuizOption("try_tasks", "Попробовать задачи", "хочет сравнить направления через простые практические задания", "пробы задач"),
                QuizOption("compare_roles", "Сравнить роли", "хочет понять разницу между профессиями и требованиями", "сравнение ролей"),
                QuizOption("choose_first_track", "Выбрать первый трек", "хочет выбрать одно направление для старта", "выбор трека"),
            ),
        )

    return QuizQuestion(
        code="skill_focus",
        title="Что нужно получить на выходе?",
        subtitle="Выбери ближайший понятный результат.",
        profile_key="focus",
        options=(
            QuizOption("understand_basics", "Понять основы", "хочет спокойно разобраться в базе", "понимание базы"),
            QuizOption("do_by_myself", "Начать делать самому", "хочет перейти от просмотра к самостоятельной практике", "самостоятельная практика"),
            QuizOption("first_result", "Сделать первый результат", "хочет получить первый готовый результат", "первый результат"),
            QuizOption("next_level", "Понять следующий шаг", "хочет понять, куда развиваться дальше", "следующий шаг"),
        ),
    )


def _level_question(profile: dict[str, str]) -> QuizQuestion:
    interest_group = _interest_group(profile.get("interest_code"))
    if interest_group == "tech":
        return QuizQuestion(
            code="tech_level",
            title="Сколько практики уже было в IT / ИИ?",
            subtitle="Честная стартовая точка экономит недели на неподходящих материалах.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Почти с нуля", "нет опыта в IT / ИИ, нужна база", "бережный старт"),
                QuizOption("tutorials", "📺 Смотрел уроки", "смотрел уроки, но мало практиковался", "переход к практике"),
                QuizOption("project", "🛠 Делал проект", "уже делал учебный или личный проект", "проектное усиление"),
                QuizOption("work", "💼 Есть рабочий опыт", "есть рабочий или коммерческий опыт", "рост уровня"),
            ),
        )

    if interest_group == "creative":
        return QuizQuestion(
            code="creative_level",
            title="Какой у тебя опыт в креативе?",
            subtitle="Поймем, нужна база, практика или упаковка работ.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Только начинаю", "начинает креативное направление с нуля", "бережный старт"),
                QuizOption("templates", "🧩 Повторял по примерам", "повторял шаблоны и туториалы", "от шаблонов к стилю"),
                QuizOption("own_works", "🎨 Есть свои работы", "уже создает собственные работы", "упаковка практики"),
                QuizOption("paid", "💸 Были заказы", "уже делал работы для других людей или клиентов", "коммерческий рост"),
            ),
        )

    if interest_group == "business":
        return QuizQuestion(
            code="business_level",
            title="Какой опыт в проектах и деньгах?",
            subtitle="Маршрут будет разным для теории, первого запуска и роста реального проекта.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Пока теория", "пока нет практики в бизнесе или маркетинге", "бережный старт"),
                QuizOption("cases", "📌 Разбирал кейсы", "изучал кейсы и материалы, но мало делал сам", "переход к действию"),
                QuizOption("small_project", "🛠 Был мини-проект", "запускал небольшой проект или тест", "проектное усиление"),
                QuizOption("sales", "📈 Уже продавал", "есть опыт продаж, маркетинга или роста проекта", "ускорение результата"),
            ),
        )

    if interest_group == "communications":
        return QuizQuestion(
            code="communications_level",
            title="Какой опыт с языками или общением?",
            subtitle="Здесь важны практика, обратная связь и регулярность.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Стесняюсь начинать", "нужен мягкий старт и понятные упражнения", "бережный старт"),
                QuizOption("basic", "🗣 Есть база", "есть базовые знания, но не хватает практики", "разговорная практика"),
                QuizOption("practice", "🎤 Уже практикуюсь", "регулярно практикуется и хочет расти быстрее", "усиление практики"),
                QuizOption("advanced", "⚡ Нужен уровень выше", "нужна продвинутая коммуникация и уверенность", "продвинутый рост"),
            ),
        )

    if interest_group == "science":
        return QuizQuestion(
            code="science_level",
            title="Какой опыт в точных задачах?",
            subtitle="Подберем баланс теории, задач и проектов.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Нужна база", "нужна понятная база в научной или инженерной теме", "бережный старт"),
                QuizOption("school_base", "📘 Есть школьная база", "есть базовая подготовка и нужно больше структуры", "сборка системы"),
                QuizOption("tasks", "🧮 Решал задачи", "уже решал задачи и хочет углубиться", "практический рост"),
                QuizOption("research", "🔬 Делал исследование", "есть проектный или исследовательский опыт", "исследовательский рост"),
            ),
        )

    if interest_group == "care":
        return QuizQuestion(
            code="care_level",
            title="Какой опыт в заботе, здоровье или работе с животными?",
            subtitle="Для таких сфер важны база, безопасность, практика и понимание ответственности.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Только интересуюсь", "пока нет опыта, нужна безопасная база и обзор сферы", "бережный старт"),
                QuizOption("home_practice", "🐾 Есть бытовой опыт", "есть личный опыт ухода, наблюдений или помощи дома", "осознанная база"),
                QuizOption("courses", "📚 Учился по материалам", "изучал курсы, книги, лекции или профильные материалы", "сборка системы"),
                QuizOption("practice", "🩺 Была практика", "есть волонтерство, стажировка, практика или работа рядом со специалистами", "практический рост"),
            ),
        )

    if interest_group == "food_craft":
        return QuizQuestion(
            code="food_craft_level",
            title="Какой опыт в кулинарии, сервисе или ремесле?",
            subtitle="Здесь маршрут должен быстро переводить знания в повторяемую практику.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Начинаю с нуля", "пока нет опыта и нужна понятная база", "бережный старт"),
                QuizOption("home_practice", "🍳 Пробовал дома", "есть бытовая практика, но не хватает системы", "домашняя практика"),
                QuizOption("repeatable", "🛠 Уже получается", "есть повторяемые результаты и хочется стабильности", "закрепление навыка"),
                QuizOption("paid", "💸 Были заказы / смены", "есть опыт заказов, смен, клиентов или прикладной работы", "коммерческий рост"),
            ),
        )

    if interest_group == "undecided":
        return QuizQuestion(
            code="direction_level",
            title="Что уже пробовал(а), чтобы выбрать направление?",
            subtitle="Если сфера еще не выбрана, маршрут начнется с коротких проб и сравнения вариантов.",
            profile_key="level",
            options=(
                QuizOption("zero", "🌱 Пока ничего", "пока не пробовал направления и хочет начать с обзора", "мягкий обзор"),
                QuizOption("watched", "📺 Смотрел обзоры", "смотрел видео, статьи или истории специалистов", "переход к пробам"),
                QuizOption("tried", "🛠 Пробовал пару задач", "уже пробовал отдельные задачи в разных сферах", "сравнение практики"),
                QuizOption("almost", "🎯 Почти выбрал", "почти выбрал направление и хочет проверить решение", "проверка направления"),
            ),
        )

    return QuizQuestion(
        code="general_level",
        title="Что уже умеешь в этой сфере?",
        subtitle="Так маршрут не будет слишком легким или слишком жестким.",
        profile_key="level",
        options=(
            QuizOption("zero", "🌱 С нуля", "пока нет опыта и нужна понятная база", "бережный старт"),
            QuizOption("basic", "⚡ Что-то пробовал", "есть базовый опыт, но не хватает системы", "сборка системы"),
            QuizOption("practice", "🛠 Делал практику", "есть практический опыт и нужен следующий уровень", "ускорение практики"),
            QuizOption("advanced", "🚀 Хочу сильнее", "уже уверенно практикуется и хочет быстрый рост", "продвинутый рост"),
        ),
    )


def _interest_group(interest_code: str | None) -> str:
    tech = {
        "tech",
        "ai_engineer",
        "ai_tools",
        "data_analyst",
        "data_excel_sql",
        "cybersecurity",
        "web_developer",
        "python",
        "programming_exam",
    }
    creative = {"creative", "ux_ui_designer", "figma_design", "video_content", "design_portfolio", "creative_tech"}
    business = {
        "business",
        "digital_marketer",
        "project_manager",
        "marketing_ads",
        "project_management",
        "social_economics",
    }
    communications = {"communications", "english_speaking", "english_exam", "russian_writing", "people_communication"}
    science = {"science", "math_exam", "chemistry", "research_project", "solar_electrician"}
    care = {"care", "healthcare_vet_assistant", "animal_care", "biology_vet", "health_nature"}
    food_craft = {"food_craft", "chef_pastry", "cooking_basics", "hands_on"}
    undecided = {"undecided", "study_planning", "productivity", "analytics_logic", "business_media"}

    if interest_code in tech:
        return "tech"
    if interest_code in creative:
        return "creative"
    if interest_code in business:
        return "business"
    if interest_code in communications:
        return "communications"
    if interest_code in science:
        return "science"
    if interest_code in care:
        return "care"
    if interest_code in food_craft:
        return "food_craft"
    if interest_code in undecided:
        return "undecided"
    return "general"


def _time_question(profile: dict[str, str]) -> QuizQuestion:
    goal_code = profile.get("goal_code")
    age_code = profile.get("age_code")
    focus_code = profile.get("focus_code")

    if age_code == "14_17" or goal_code == "exam":
        options = (
            QuizOption("micro", "⏱ 10-15 мин в день", "готов выделять 10-15 минут в день", "микро-спринты"),
            QuizOption("daily", "📚 30 мин после учебы", "готов выделять около 30 минут после учебы", "учебный ритм"),
            QuizOption("weekend", "🗓 Больше на выходных", "готов учиться в основном на выходных", "выходной формат"),
            QuizOption("intensive", "🚀 Интенсив перед дедлайном", "готов учиться интенсивно перед дедлайном", "интенсив"),
        )
    elif goal_code == "career" or focus_code in {"internship", "junior", "switch"}:
        options = (
            QuizOption("daily", "⚡ 30 мин в день", "готов выделять 30 минут в день", "ежедневный ритм"),
            QuizOption("weekly", "🗓 3-4 часа в неделю", "готов выделять 3-4 часа в неделю", "недельные блоки"),
            QuizOption("intensive", "🚀 1-2 часа в день", "готов учиться интенсивно по 1-2 часа в день", "интенсив"),
            QuizOption("weekend", "💼 Спринт по выходным", "готов делать карьерные спринты по выходным", "выходной формат"),
        )
    else:
        options = (
            QuizOption("micro", "⏱ 10-15 мин в день", "готов выделять 10-15 минут в день", "микро-спринты"),
            QuizOption("daily", "⚡ 20-30 мин в день", "готов выделять 20-30 минут в день", "ежедневный ритм"),
            QuizOption("weekly", "🗓 3-4 часа в неделю", "готов выделять 3-4 часа в неделю", "недельные блоки"),
            QuizOption("intensive", "🚀 Хочу интенсив", "готов учиться интенсивно и быстрее двигаться", "интенсив"),
        )

    return QuizQuestion(
        code="time",
        title="Сколько времени реально готов(а) выделять?",
        subtitle="Лучший маршрут тот, который помещается в жизнь, а не ломает ее.",
        profile_key="time",
        options=options,
    )


def _constraint_question(profile: dict[str, str]) -> QuizQuestion:
    time_code = profile.get("time_code")
    if time_code == "micro":
        return QuizQuestion(
            code="micro_constraints",
            title="Что поможет не сорваться в коротком формате?",
            subtitle="Соберем маршрут так, чтобы он работал даже при плотном графике.",
            profile_key="constraints",
            multi_select=True,
            options=(
                QuizOption("tiny_steps", "🔹 Очень короткие шаги", "нужны сверхкороткие шаги без перегруза", "ультракороткий формат"),
                QuizOption("reminders", "🔔 Напоминания", "нужны напоминания и мягкий ритм", "ритм поддержки"),
                QuizOption("weekend", "🗓 Добор на выходных", "нужно переносить часть практики на выходные", "гибкий график"),
                QuizOption("no_video", "📄 Больше текста", "нужны материалы, которые быстро читаются без длинных видео", "быстрые материалы"),
            ),
        )

    if time_code == "intensive":
        return QuizQuestion(
            code="intensive_constraints",
            title="Какой формат ускорит тебя сильнее?",
            subtitle="Для интенсивного режима важны фокус и быстрые проверки результата.",
            profile_key="constraints",
            multi_select=True,
            options=(
                QuizOption("deadline", "⏳ Дедлайны", "нужны четкие дедлайны и контрольные точки", "дедлайн-режим"),
                QuizOption("practice", "🛠 Больше практики", "нужен максимум практики и минимум лишней теории", "практический режим"),
                QuizOption("mentor", "👀 Обратная связь", "нужна обратная связь по ошибкам и работам", "режим обратной связи"),
                QuizOption("portfolio", "📁 Портфолио", "нужно быстро собрать видимый результат", "портфолио-режим"),
            ),
        )

    return QuizQuestion(
        code="constraints",
        title="Что мешает или какой формат нужен?",
        subtitle="Это последнее уточнение влияет на материалы, практику и поддержку мотивации.",
        profile_key="constraints",
        multi_select=True,
        options=(
            QuizOption("chaos", "🧩 Много хаоса", "нужны последовательность, фильтр материалов и понятные шаги", "антихаос"),
            QuizOption("motivation", "🔥 Падает мотивация", "нужны быстрые победы, видимый прогресс и поддержка", "ритм мотивации"),
            QuizOption("hard", "🧱 Сложно понять базу", "нужны простые объяснения и постепенное усложнение", "мягкая база"),
            QuizOption("no_practice", "🛠 Мало практики", "нужны задания и применение после каждого блока", "практический ритм"),
        ),
    )


def _base_result(goal_code: str) -> dict[str, str]:
    if goal_code == "career":
        return {
            "hero": "Карьерный маршрут",
            "reason": "Связывает обучение с ближайшим карьерным шагом.",
        }
    if goal_code == "exam":
        return {
            "hero": "Учебный маршрут",
            "reason": "Разбивает учебную цель на темы, практику и самопроверку.",
        }
    if goal_code == "explore":
        return {
            "hero": "Подбор направлений",
            "reason": "Помогает выбрать несколько специальностей для короткой проверки.",
        }
    return {
        "hero": "Маршрут навыка",
        "reason": "Собирает обучение вокруг конкретного навыка и результата, который можно применить.",
    }


def _hero_name(base_hero: str, time_code: str, constraint_codes: set[str]) -> str:
    if time_code == "micro":
        return "Маршрут короткими шагами"
    if time_code == "intensive":
        return "Интенсивный маршрут"
    if "motivation" in constraint_codes:
        return "Маршрут с поддержкой ритма"
    if "chaos" in constraint_codes:
        return "Маршрут без хаоса"
    return base_hero


def _how_to_use(time_code: str, goal_code: str) -> str:
    if time_code == "micro":
        return "Проходи один маленький шаг в день: 10 минут на материал и 5 минут на мини-действие."
    if time_code == "intensive":
        return "Двигайся спринтами: цель недели, практика каждый день, контрольный результат в конце блока."
    if goal_code == "career":
        return "Каждую неделю связывай новый навык с карьерным артефактом: кейсом, профилем или тестовым заданием."
    if goal_code == "explore":
        return "Сначала сравни 3-5 направлений через короткие пробы, затем выбери один трек для обучения."
    return "Иди блоками: короткая теория, практика, самопроверка и следующий шаг без накопления лишних материалов."


def _profile_value(profile: dict[str, str], key: str, *fallback_keys: str) -> str:
    return escape(_profile_value_raw(profile, key, *fallback_keys))


def _profile_value_raw(profile: dict[str, str], key: str, *fallback_keys: str) -> str:
    for candidate in (key, *fallback_keys):
        value = profile.get(candidate)
        if value:
            return str(value)
    return "не указано"
