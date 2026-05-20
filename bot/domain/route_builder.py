from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_personal_route(
    profile: dict[str, str],
    *,
    reason: str | None = None,
    previous_route: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a deterministic MVP route without LLM calls.

    The route is intentionally small: it gives the user the minimum useful path
    to a first result and keeps all materials free, online, and Russian-language.
    """

    track = choose_track(profile)
    modules = deepcopy(ROUTE_TEMPLATES[track])
    modules = adapt_route(modules, profile)

    if reason:
        modules = rebuild_route(modules, reason, previous_route or [])

    return modules


def choose_track(profile: dict[str, str]) -> str:
    text = " ".join(str(value).casefold() for value in profile.values())
    if any(word in text for word in ("python", "питон", "программ", "код", "сайт", "frontend", "фронтенд")):
        return "python"
    if any(word in text for word in ("англий", "english", "travel", "путешеств", "разговор")):
        return "english"
    if any(word in text for word in ("готов", "кулинар", "ужин", "еда", "выпеч")):
        return "cooking"
    if any(word in text for word in ("дизайн", "figma", "маркет", "контент", "smm")):
        return "digital"
    return "universal"


def adapt_route(modules: list[dict[str, Any]], profile: dict[str, str]) -> list[dict[str, Any]]:
    time_text = str(profile.get("time") or profile.get("time_code") or "").casefold()
    level_text = str(profile.get("level") or profile.get("level_code") or "").casefold()
    goal_text = str(profile.get("goal") or profile.get("focus") or "").casefold()

    if any(marker in time_text for marker in ("1", "2", "мало", "час")):
        modules = modules[:3]
        for module in modules:
            module["duration"] = "короткий шаг"
            module["materials"] = module.get("materials", [])[:2]

    if any(marker in level_text for marker in ("опыт", "basic", "intermediate", "уже")) and len(modules) > 3:
        modules = modules[1:]
        modules[0]["title"] = f"{modules[0]['title']} без повторения очевидного"

    if any(marker in goal_text for marker in ("работ", "карьер", "професс", "портфолио")):
        modules.append(PORTFOLIO_MODULE)

    return modules[:5]


def rebuild_route(
    modules: list[dict[str, Any]],
    reason: str,
    previous_route: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_reason = reason.casefold()
    next_modules = deepcopy(modules)

    if "hard" in normalized_reason or "сложно" in normalized_reason:
        for module in next_modules:
            module["title"] = f"Мягкий старт: {module['title']}"
            module["duration"] = "маленький шаг"
            module["materials"] = [intro_material(), *module.get("materials", [])[:1]]
        return next_modules[:4]

    if "easy" in normalized_reason or "просто" in normalized_reason:
        for module in next_modules:
            module["materials"] = [*module.get("materials", []), practice_material()]
        next_modules.append(PORTFOLIO_MODULE)
        return next_modules[:5]

    if "replace" in normalized_reason or "format" in normalized_reason or "замен" in normalized_reason:
        for module in next_modules:
            module["materials"] = rotate_materials(module.get("materials", []))
        return next_modules

    if previous_route:
        return previous_route
    return next_modules


def rotate_materials(materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(materials) < 2:
        return [replacement_material(), *materials]
    return [materials[-1], *materials[:-1]]


def material(kind: str, title: str, source: str, duration: str, interaction: str, url: str) -> dict[str, str]:
    return {
        "kind": kind,
        "title": title,
        "source": source,
        "duration": duration,
        "interaction": interaction,
        "url": url,
        "language": "ru",
        "is_free": True,
    }


def intro_material() -> dict[str, str]:
    return material(
        "Статья",
        "Вводное объяснение простыми словами",
        "Открытый русскоязычный материал",
        "10 минут",
        "Прочитать и выписать 3 непонятных слова.",
        "https://ru.wikipedia.org/wiki/Самообразование",
    )


def replacement_material() -> dict[str, str]:
    return material(
        "Видео",
        "Альтернативное объяснение темы",
        "YouTube",
        "15 минут",
        "Посмотреть и отметить, стало ли понятнее.",
        "https://www.youtube.com/results?search_query=обучение+с+нуля",
    )


def practice_material() -> dict[str, str]:
    return material(
        "Практика",
        "Усложненное практическое задание",
        "Открытый тренажер",
        "35 минут",
        "Сделать один самостоятельный пример и сохранить результат.",
        "https://stepik.org/catalog",
    )


PORTFOLIO_MODULE = {
    "title": "Портфолио и следующий карьерный шаг",
    "description": "Собрать результат в понятный артефакт: проект, чек-лист, подборку работ или короткое описание навыков.",
    "duration": "1 неделя",
    "outcome": "Появится результат, который можно показать наставнику, преподавателю или работодателю.",
    "practice": "Описать цель, что сделано, какие навыки применены и что будет следующим шагом.",
    "checkpoint": "Готова карточка результата для портфолио.",
    "skills": ["портфолио", "самопрезентация", "рефлексия"],
    "materials": [
        material(
            "Статья",
            "Как оформить учебный проект в портфолио",
            "Хабр Карьера",
            "15 минут",
            "Собрать описание проекта по шаблону.",
            "https://career.habr.com/journal",
        )
    ],
}


ROUTE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "python": [
        {
            "title": "Старт в программировании",
            "description": "Понять, что такое программа, как запускать код и зачем нужен Python.",
            "duration": "1 неделя",
            "outcome": "Пользователь запускает первый код и понимает базовые термины.",
            "practice": "Установить среду или открыть онлайн-интерпретатор и вывести строку о себе.",
            "checkpoint": "Первый запуск Python выполнен.",
            "skills": ["Python", "запуск кода", "базовые понятия"],
            "materials": [
                material("Курс", "Поколение Python: курс для начинающих", "Stepik", "2-3 часа", "Пройти первые уроки и решить стартовые задачи.", "https://stepik.org/course/58852/promo"),
                material("Видео", "Python для начинающих", "YouTube", "20 минут", "Повторить пример из видео.", "https://www.youtube.com/results?search_query=python+для+начинающих+с+нуля"),
            ],
        },
        {
            "title": "Переменные, условия и циклы",
            "description": "Научиться хранить данные и управлять логикой программы.",
            "duration": "1-2 недели",
            "outcome": "Можно написать простую программу с вводом, условиями и повторением действий.",
            "practice": "Сделать мини-калькулятор или опросник.",
            "checkpoint": "Программа использует переменные, if и цикл.",
            "skills": ["переменные", "условия", "циклы"],
            "materials": [
                material("Курс", "Основы Python", "Stepik", "3 часа", "Решить задачи по условиям и циклам.", "https://stepik.org/catalog?search=python%20основы"),
                material("Статья", "Python: условия и циклы", "pythonworld.ru", "25 минут", "Разобрать примеры и изменить их под свою задачу.", "https://pythonworld.ru/osnovy"),
            ],
        },
        {
            "title": "Списки, функции и мини-проект",
            "description": "Собрать первый полезный учебный проект из нескольких функций.",
            "duration": "2 недели",
            "outcome": "Готов небольшой проект: список задач, викторина или помощник для расчетов.",
            "practice": "Собрать проект, сохранить код и описать, как им пользоваться.",
            "checkpoint": "Мини-проект работает от начала до конца.",
            "skills": ["списки", "функции", "мини-проект"],
            "materials": [
                material("Практика", "Задачи по Python для начинающих", "Stepik", "2 часа", "Решить 8-10 задач на списки и функции.", "https://stepik.org/catalog?search=python%20задачи"),
                material("Видео", "Мини-проект на Python", "YouTube", "30 минут", "Повторить идею и изменить под себя.", "https://www.youtube.com/results?search_query=мини+проект+python+для+начинающих"),
            ],
        },
    ],
    "english": [
        {
            "title": "Базовые фразы для поездки",
            "description": "Собрать набор фраз для приветствия, просьб и простых вопросов.",
            "duration": "1 неделя",
            "outcome": "Пользователь может начать короткий бытовой диалог.",
            "practice": "Записать 10 фраз голосом и повторить вслух.",
            "checkpoint": "Фразы произносятся без чтения с экрана.",
            "skills": ["greetings", "requests", "pronunciation"],
            "materials": [
                material("Видео", "Английский для путешествий", "YouTube", "25 минут", "Повторить диалоги вслух.", "https://www.youtube.com/results?search_query=английский+для+путешествий"),
                material("Статья", "Разговорник английского для туриста", "Puzzle English", "20 минут", "Собрать личный мини-разговорник.", "https://puzzle-english.com/directory/travel"),
            ],
        },
        {
            "title": "Аэропорт, отель, кафе",
            "description": "Разобрать самые частые ситуации поездки.",
            "duration": "2 недели",
            "outcome": "Пользователь понимает типовые вопросы и может ответить короткими фразами.",
            "practice": "Разыграть 3 диалога: регистрация, заселение, заказ еды.",
            "checkpoint": "Три сценария пройдены без подсказки.",
            "skills": ["airport", "hotel", "cafe"],
            "materials": [
                material("Подборка", "Английский в аэропорту", "YouTube", "20 минут", "Повторить фразы по ролям.", "https://www.youtube.com/results?search_query=английский+в+аэропорту"),
                material("Видео", "Английский в кафе", "YouTube", "15 минут", "Составить свой заказ.", "https://www.youtube.com/results?search_query=английский+в+кафе"),
            ],
        },
        {
            "title": "Тренировка живого диалога",
            "description": "Закрепить маршрут через повторение и мини-тесты.",
            "duration": "1 неделя",
            "outcome": "Есть уверенность в базовых бытовых сценариях.",
            "practice": "Провести 5 коротких тренировочных диалогов.",
            "checkpoint": "Пользователь может объяснить простую проблему в поездке.",
            "skills": ["dialogue", "listening", "confidence"],
            "materials": [
                material("Практика", "Тренировка разговорного английского", "Lingualeo", "30 минут", "Пройти короткую тренировку слов и фраз.", "https://lingualeo.com/ru"),
                material("Видео", "Диалоги на английском для начинающих", "YouTube", "20 минут", "Повторить два диалога.", "https://www.youtube.com/results?search_query=диалоги+на+английском+для+начинающих"),
            ],
        },
    ],
    "cooking": [
        {
            "title": "Безопасность и базовая подготовка",
            "description": "Научиться безопасно работать с ножом, плитой и продуктами.",
            "duration": "1 неделя",
            "outcome": "Пользователь готовит рабочее место и не теряется на кухне.",
            "practice": "Нарезать овощи тремя способами и подготовить простую заготовку.",
            "checkpoint": "Рабочее место собрано, базовая нарезка получается стабильно.",
            "skills": ["безопасность", "нарезка", "подготовка"],
            "materials": [
                material("Видео", "Базовые техники нарезки", "YouTube", "15 минут", "Повторить на одном овощe.", "https://www.youtube.com/results?search_query=базовые+техники+нарезки"),
                material("Статья", "Основы безопасности на кухне", "Открытый материал", "10 минут", "Составить чек-лист перед готовкой.", "https://ru.wikipedia.org/wiki/Кулинария"),
            ],
        },
        {
            "title": "Простые ужины",
            "description": "Освоить 3-4 базовых блюда без сложных техник.",
            "duration": "2 недели",
            "outcome": "Можно приготовить ужин из доступных продуктов.",
            "practice": "Приготовить пасту, крупу с белком и овощное блюдо.",
            "checkpoint": "Три ужина приготовлены и оценены по вкусу/времени.",
            "skills": ["варка", "жарка", "баланс блюда"],
            "materials": [
                material("Видео", "Простые ужины на каждый день", "YouTube", "25 минут", "Выбрать один рецепт и приготовить.", "https://www.youtube.com/results?search_query=простые+ужины+на+каждый+день"),
                material("Подборка", "Рецепты простых ужинов", "Еда.ру", "30 минут", "Собрать список из 5 рецептов.", "https://eda.ru/recepty"),
            ],
        },
        {
            "title": "Планирование меню",
            "description": "Научиться планировать покупки и повторять удачные блюда.",
            "duration": "1 неделя",
            "outcome": "Есть простое меню на неделю и список покупок.",
            "practice": "Составить меню на 3 дня и купить продукты по списку.",
            "checkpoint": "Меню повторяемо без постоянного поиска рецептов.",
            "skills": ["меню", "покупки", "экономия"],
            "materials": [
                material("Статья", "Как планировать меню", "Открытый материал", "15 минут", "Составить свое меню на 3 дня.", "https://www.google.com/search?q=как+планировать+меню+на+неделю"),
                material("Практика", "Шаблон списка покупок", "Открытый шаблон", "20 минут", "Заполнить список под свои блюда.", "https://www.google.com/search?q=шаблон+списка+покупок+меню"),
            ],
        },
    ],
    "digital": [
        {
            "title": "Цель и референсы",
            "description": "Понять задачу и собрать примеры хороших решений.",
            "duration": "1 неделя",
            "outcome": "Есть понятное направление и критерии результата.",
            "practice": "Собрать 10 референсов и объяснить, что в них работает.",
            "checkpoint": "Готова доска референсов.",
            "skills": ["анализ", "референсы", "критерии"],
            "materials": [
                material("Видео", "Как искать референсы", "YouTube", "15 минут", "Собрать подборку примеров.", "https://www.youtube.com/results?search_query=как+искать+референсы+дизайн"),
                material("Статья", "Основы визуального анализа", "Открытый материал", "20 минут", "Описать 5 найденных примеров.", "https://ru.wikipedia.org/wiki/Дизайн"),
            ],
        },
        {
            "title": "Первый макет или контент-план",
            "description": "Сделать первый прикладной результат в выбранной digital-сфере.",
            "duration": "2 недели",
            "outcome": "Готов черновик макета, поста, лендинга или рекламной идеи.",
            "practice": "Собрать одну законченную работу и показать ее другому человеку.",
            "checkpoint": "Есть первая версия результата.",
            "skills": ["прототип", "контент", "обратная связь"],
            "materials": [
                material("Курс", "Основы дизайна и интерфейсов", "Stepik", "2 часа", "Пройти стартовые уроки.", "https://stepik.org/catalog?search=дизайн"),
                material("Видео", "Figma для начинающих", "YouTube", "25 минут", "Повторить простой экран.", "https://www.youtube.com/results?search_query=figma+для+начинающих"),
            ],
        },
        PORTFOLIO_MODULE,
    ],
    "universal": [
        {
            "title": "Уточнение цели",
            "description": "Сузить интерес до конкретного первого результата.",
            "duration": "1 неделя",
            "outcome": "Понятно, чему учиться первым и зачем.",
            "practice": "Записать цель, ограничения и критерии готовности.",
            "checkpoint": "Сформулирован первый измеримый результат.",
            "skills": ["цель", "план", "самообучение"],
            "materials": [intro_material()],
        },
        {
            "title": "База и практика",
            "description": "Освоить минимальный набор понятий и сразу применить их.",
            "duration": "1-2 недели",
            "outcome": "Есть первый практический опыт без перегруза.",
            "practice": "Сделать 3 коротких упражнения по выбранной теме.",
            "checkpoint": "Понятно, что получается, а что нужно заменить.",
            "skills": ["база", "практика", "обратная связь"],
            "materials": [replacement_material(), practice_material()],
        },
        PORTFOLIO_MODULE,
    ],
}
