"""Заглушечный контент курса и сериализация маршрута."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha1
from typing import Any


@dataclass(frozen=True)
class CourseMaterial:
    """Материал внутри модуля маршрута."""

    kind: str
    title: str
    source: str
    duration: str
    interaction: str


@dataclass(frozen=True)
class CourseModule:
    """Один последовательный модуль образовательного маршрута."""

    title: str
    duration: str
    outcome: str
    description: str
    materials: tuple[CourseMaterial, ...]
    practice: str
    skills: tuple[str, ...]
    career_link: str


def build_course(profile: dict[str, str]) -> tuple[CourseModule, ...]:
    """Собирает персональный маршрут из заглушек по уже собранному профилю."""

    interest = _clean_profile_value(profile.get("interest", "выбранная сфера"))
    focus = _clean_profile_value(profile.get("focus", "первый видимый результат"))
    level = _clean_profile_value(profile.get("level", "стартовый уровень"))
    time = _clean_profile_value(profile.get("time", "20-30 минут в день"))
    goal_code = profile.get("goal_code", "skill")

    if goal_code == "explore":
        specialties = recommended_specialties(profile)
        specialties_text = ", ".join(specialties[:5])
        return (
            CourseModule(
                title="Модуль 1. Подбор направлений",
                duration=_duration(time, "30-40 минут"),
                outcome=f"Получить короткий список специальностей: {specialties_text}.",
                description="Сначала сравниваем несколько вариантов, а не выбираем профессию вслепую.",
                materials=(
                    CourseMaterial(
                        kind="Обзор",
                        title="Карта новых специальностей",
                        source="Бесплатный русскоязычный источник",
                        duration="12 минут",
                        interaction="Отметить 2-3 направления, которые хочется проверить.",
                    ),
                    CourseMaterial(
                        kind="Сравнение",
                        title="Что делают специалисты на практике",
                        source="Открытый видеоразбор или статья",
                        duration="15 минут",
                        interaction="Сравнить задачи, входной уровень и формат работы.",
                    ),
                ),
                practice=f"Выбрать 3 направления из списка: {specialties_text}.",
                skills=("выбор направления", "сравнение ролей", "оценка интереса"),
                career_link="Практическая польза: помогает сузить выбор до нескольких проверяемых вариантов.",
            ),
            CourseModule(
                title="Модуль 2. Быстрые пробы задач",
                duration=_duration(time, "45-60 минут"),
                outcome="Попробовать простые задания из разных направлений.",
                description="Короткая практика показывает больше, чем описание профессии.",
                materials=(
                    CourseMaterial(
                        kind="Практикум",
                        title="Мини-задачи по выбранным направлениям",
                        source="Открытые русскоязычные материалы",
                        duration="30 минут",
                        interaction="Сделать по одной простой задаче на каждое направление.",
                    ),
                    CourseMaterial(
                        kind="Чек-лист",
                        title="Как понять, что направление подходит",
                        source="Открытая методичка",
                        duration="10 минут",
                        interaction="Оценить интерес, сложность и желание продолжать.",
                    ),
                ),
                practice="Заполнить таблицу: что понравилось, что было трудно, куда хочется вернуться.",
                skills=("самопроверка", "практическое сравнение", "осознанный выбор"),
                career_link="Практическая польза: помогает выбрать направление через реальные задачи.",
            ),
            CourseModule(
                title="Модуль 3. Первый трек",
                duration=_duration(time, "40-60 минут"),
                outcome="Выбрать одно направление для старта.",
                description="На этом шаге фиксируем не окончательную профессию, а первый трек для ближайших недель.",
                materials=(
                    CourseMaterial(
                        kind="Подборка",
                        title="Стартовые материалы по выбранному направлению",
                        source="Бесплатные русскоязычные курсы, видео или статьи",
                        duration="20 минут",
                        interaction="Выбрать один материал для первой недели.",
                    ),
                    CourseMaterial(
                        kind="План",
                        title="Первые 7 дней обучения",
                        source="Шаблон маршрута",
                        duration="10 минут",
                        interaction="Запланировать 3 коротких учебных действия.",
                    ),
                ),
                practice="Сформулировать первый трек: направление, цель недели и первый материал.",
                skills=("планирование", "фокус", "выбор стартового материала"),
                career_link="Практическая польза: превращает список профессий в один понятный следующий шаг.",
            ),
        )

    return (
        CourseModule(
            title="Модуль 1. Старт и цель",
            duration=_duration(time, "35-45 минут"),
            outcome="Понять стартовую точку и ближайший результат.",
            description=(
                f"Тема: {interest}. Стартовый уровень: {level}. "
                "На этом шаге фиксируем цель и убираем лишние материалы."
            ),
            materials=(
                CourseMaterial(
                    kind="Короткая лекция",
                    title=f"Обзор направления «{interest}»",
                    source="Бесплатный русскоязычный видеоразбор",
                    duration="12 минут",
                    interaction="Посмотреть и выписать 3 задачи, которые хочется научиться делать.",
                ),
                CourseMaterial(
                    kind="Статья",
                    title="Словарь новичка и карта тем",
                    source="Открытая русскоязычная статья",
                    duration="10 минут",
                    interaction="Отметить непонятные термины и выбрать 2 темы для углубления.",
                ),
            ),
            practice=f"Сформулировать личную мини-цель: какой результат в теме «{interest}» будет готов в конце курса.",
            skills=("самодиагностика", "постановка учебной цели", "фильтрация материалов"),
            career_link=_career_link(goal_code, "понимать, какие задачи реально стоят за направлением"),
        ),
        CourseModule(
            title="Модуль 2. База направления",
            duration=_duration(time, "50-70 минут"),
            outcome="Освоить базовые понятия и не перескочить к сложным материалам слишком рано.",
            description="Короткая теория, проверка понимания и первые понятные действия.",
            materials=(
                CourseMaterial(
                    kind="Мини-курс",
                    title=f"Базовый курс по теме «{interest}»",
                    source="Stepik / Открытое образование / другой бесплатный источник",
                    duration="25 минут",
                    interaction="Пройти первый раздел и сохранить 5 ключевых тезисов.",
                ),
                CourseMaterial(
                    kind="Видео",
                    title="Разбор частых ошибок новичков",
                    source="YouTube / VK Видео / RuTube",
                    duration="15 минут",
                    interaction="Сравнить ошибки с собственным опытом и отметить одну зону риска.",
                ),
            ),
            practice="Сделать короткий конспект: что уже понятно, что требует повторения, что можно применить сразу.",
            skills=("понимание базы", "учебная самопроверка", "работа с конспектом"),
            career_link=_career_link(goal_code, "разбирать простые задачи и не теряться в терминологии"),
        ),
        CourseModule(
            title="Модуль 3. Практика",
            duration=_duration(time, "60-90 минут"),
            outcome=f"Сделать практическую работу под результат: {focus}.",
            description="Переходим от просмотра к действию и собираем первый видимый результат.",
            materials=(
                CourseMaterial(
                    kind="Практикум",
                    title=f"Пошаговое задание по теме «{interest}»",
                    source="Открытый практический материал на русском языке",
                    duration="35 минут",
                    interaction="Повторить пример, затем изменить его под свою цель.",
                ),
                CourseMaterial(
                    kind="Чек-лист",
                    title="Критерии качества первой работы",
                    source="Открытая подборка или методичка",
                    duration="10 минут",
                    interaction="Проверить работу по чек-листу и записать 2 улучшения.",
                ),
            ),
            practice=f"Собрать черновик результата: {focus}.",
            skills=("прикладная практика", "самопроверка", "итерационное улучшение"),
            career_link=_career_link(goal_code, "показывать первый результат в портфолио, учебном проекте или собеседовании"),
        ),
        CourseModule(
            title="Модуль 4. Итог и следующий шаг",
            duration=_duration(time, "40-60 минут"),
            outcome="Зафиксировать прогресс, получить достижение и понять, куда двигаться дальше.",
            description="Фиксируем результат и выбираем следующий учебный шаг.",
            materials=(
                CourseMaterial(
                    kind="Подборка",
                    title=f"Следующие бесплатные материалы по теме «{interest}»",
                    source="Подборка русскоязычных курсов, видео и статей",
                    duration="15 минут",
                    interaction="Выбрать 1 материал для следующей недели, не добавляя лишнего.",
                ),
                CourseMaterial(
                    kind="Шаблон",
                    title="Карточка результата для Прогрессоров",
                    source="Внутренний шаблон подтверждения прогресса",
                    duration="10 минут",
                    interaction="Заполнить результат, навыки и ссылку на работу, если она есть.",
                ),
            ),
            practice="Заполнить итоговую карточку: чему научился, что получилось, что будет следующим шагом.",
            skills=("рефлексия", "упаковка результата", "планирование следующего шага"),
            career_link=_career_link(goal_code, "объяснять свой прогресс и показывать подтверждение прохождения"),
        ),
    )


def recommended_specialties(profile: dict[str, str]) -> tuple[str, ...]:
    """Возвращает короткий список специальностей для маршрута выбора направления."""

    interest_code = profile.get("interest_code", "")
    by_interest = {
        "creative_tech": ("UX/UI-дизайнер", "Дизайнер презентаций", "No-code разработчик", "Контент-дизайнер", "3D/моушн-дизайнер"),
        "analytics_logic": ("Аналитик данных", "BI-аналитик", "Продуктовый аналитик", "Тестировщик", "Специалист по автоматизации"),
        "people_communication": ("HR-специалист", "Методист онлайн-курсов", "Менеджер поддержки", "Аккаунт-менеджер", "Комьюнити-менеджер"),
        "business_media": ("SMM-специалист", "Маркетолог", "Продюсер онлайн-проектов", "Контент-менеджер", "Project manager"),
        "health_nature": ("Ветеринарный ассистент", "Лаборант", "Эко-волонтер координатор", "Медицинский регистратор", "Специалист по уходу"),
        "hands_on": ("Электромонтажник", "Повар-кондитер", "Оператор станков", "Мастер сервиса", "Техник по оборудованию"),
    }
    return by_interest.get(
        interest_code,
        ("Аналитик данных", "UX/UI-дизайнер", "SMM-специалист", "Project manager", "Тестировщик"),
    )


def serialize_course(modules: tuple[CourseModule, ...]) -> list[dict[str, Any]]:
    """Преобразует маршрут в JSON-совместимый список."""

    return [asdict(module) for module in modules]


def deserialize_course(raw_modules: Any) -> tuple[CourseModule, ...]:
    """Восстанавливает маршрут из JSON, сохраненного в SQLite."""

    if not isinstance(raw_modules, list):
        return ()

    modules: list[CourseModule] = []
    for raw_module in raw_modules:
        if not isinstance(raw_module, dict):
            continue

        raw_materials = raw_module.get("materials", [])
        materials = tuple(
            CourseMaterial(
                kind=str(material.get("kind", "Материал")),
                title=str(material.get("title", "Заглушка материала")),
                source=str(material.get("source", "Открытый источник")),
                duration=str(material.get("duration", "10 минут")),
                interaction=str(material.get("interaction", "Изучить и отметить выводы.")),
            )
            for material in raw_materials
            if isinstance(material, dict)
        )
        modules.append(
            CourseModule(
                title=str(raw_module.get("title", "Модуль курса")),
                duration=str(raw_module.get("duration", "45 минут")),
                outcome=str(raw_module.get("outcome", "Получить понятный результат.")),
                description=str(raw_module.get("description", "")),
                materials=materials,
                practice=str(raw_module.get("practice", "Выполнить практическое задание.")),
                skills=tuple(str(skill) for skill in raw_module.get("skills", []) if skill),
                career_link=str(raw_module.get("career_link", "Помогает двигаться к следующей роли или задаче.")),
            )
        )

    return tuple(modules)


def make_certificate_code(user_id: int, course_id: int) -> str:
    """Генерирует короткий код подтверждения для сертификата прототипа."""

    digest = sha1(f"progressors:{user_id}:{course_id}".encode("utf-8")).hexdigest().upper()
    return f"PRG-{digest[:4]}-{digest[4:8]}-{digest[8:12]}"


def render_qr_placeholder(certificate_code: str, size: int = 13) -> str:
    """Рисует QR-подобную заглушку подтверждения прямо в сообщении Telegram."""

    seed = sha1(certificate_code.encode("utf-8")).digest()
    rows: list[str] = []
    for y in range(size):
        cells: list[str] = []
        for x in range(size):
            finder = _finder_cell(x, y, size)
            if finder is not None:
                dark = finder
            else:
                index = (x * 17 + y * 31) % len(seed)
                dark = bool((seed[index] >> ((x + y) % 8)) & 1)
            cells.append("██" if dark else "  ")
        rows.append("".join(cells))
    return "\n".join(rows)


def extra_feature_suggestions() -> tuple[str, ...]:
    """Идеи функций для следующей итерации бота."""

    return (
        "Автозамена материалов по фидбеку: слишком сложно, слишком просто, не подошел формат.",
        "Еженедельный план с напоминаниями и мягким переносом дедлайнов.",
        "Экспорт маршрута в PDF-карту или карточку для приложения «Прогрессоры».",
        "Проверочные мини-квизы после модулей и выдача бейджей за навыки.",
        "Подбор реальных бесплатных русскоязычных материалов через каталог источников.",
        "Рекомендации карьерных ролей и учебных проектов после каждого этапа.",
        "Режим наставника: пользователь присылает работу, бот дает чек-лист обратной связи.",
        "Групповые челленджи и лидерборд по прогрессу внутри класса, вуза или команды.",
        "Интеграция с картой «Прогрессоров»: модули как точки маршрута, достижения как артефакты.",
        "Верификация загруженных сертификатов: извлечение названия, даты, платформы и статуса проверки.",
    )


def _clean_profile_value(value: str) -> str:
    """Убирает служебные префиксы из сохраненного профиля."""

    prefixes = (
        "цель пользователя:",
        "навык или специальность пользователя:",
        "возраст пользователя:",
        "ожидаемый результат:",
        "опыт и текущие навыки пользователя:",
        "готов выделять на обучение:",
        "важное ограничение:",
        "хочет ",
        "интересуется ",
        "выбирает ",
    )
    cleaned = " ".join(str(value).strip().split())
    for prefix in prefixes:
        if cleaned.casefold().startswith(prefix):
            return cleaned[len(prefix) :].strip()
    return cleaned


def _duration(time: str, default: str) -> str:
    """Адаптирует длительность модуля под заявленный темп."""

    folded = time.casefold()
    if "10-15" in folded or "микро" in folded:
        return f"{default}, можно разбить на 3-4 коротких подхода"
    if "интенсив" in folded or "1-2 часа" in folded:
        return f"{default}, лучше пройти одним спринтом"
    if "выход" in folded:
        return f"{default}, удобно пройти за один выходной блок"
    return default


def _career_link(goal_code: str, text: str) -> str:
    """Формулирует связь модуля с карьерными, учебными или личными возможностями."""

    if goal_code == "career":
        return f"Карьерная польза: помогает {text}."
    if goal_code == "exam":
        return f"Учебная польза: помогает {text}."
    return f"Практическая польза: помогает {text}."


def _finder_cell(x: int, y: int, size: int) -> bool | None:
    """Рисует три угловых маркера, чтобы заглушка выглядела как QR."""

    anchors = ((0, 0), (size - 5, 0), (0, size - 5))
    for anchor_x, anchor_y in anchors:
        if anchor_x <= x < anchor_x + 5 and anchor_y <= y < anchor_y + 5:
            local_x = x - anchor_x
            local_y = y - anchor_y
            return (
                local_x in {0, 4}
                or local_y in {0, 4}
                or (1 <= local_x <= 3 and 1 <= local_y <= 3 and local_x == 2 and local_y == 2)
            )
    return None
