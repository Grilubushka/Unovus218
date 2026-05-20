QUESTIONS = [
    {
        "key": "goal",
        "text": "Какая главная цель? Можно написать свободно.",
        "buttons": None,
    },
    {
        "key": "direction",
        "text": "Выбери направление.",
        "buttons": [
            ("Программирование", "programming"),
            ("Английский", "english"),
            ("Кулинария", "cooking"),
        ],
    },
    {
        "key": "age",
        "text": "Сколько тебе лет?",
        "buttons": [("14-17", "16"), ("18-24", "20"), ("25+", "25")],
    },
    {
        "key": "result",
        "text": "Какой результат нужен?",
        "buttons": [
            ("Быстро попробовать", "try_fast"),
            ("Сделать проект", "project"),
            ("Для работы", "career"),
        ],
    },
    {
        "key": "experience",
        "text": "Какой текущий опыт?",
        "buttons": [("Нет опыта", "none"), ("Есть база", "beginner"), ("Уверенный уровень", "intermediate")],
    },
    {
        "key": "weekly_time",
        "text": "Сколько часов в неделю готов уделять?",
        "buttons": [("1-2 часа", "2"), ("3-5 часов", "4"), ("6+ часов", "7")],
    },
    {
        "key": "motivation",
        "text": "Что важнее в подаче?",
        "buttons": [
            ("Не перегореть", "support"),
            ("Попробовать сферу", "try"),
            ("Карьерный рост", "career"),
        ],
    },
    {
        "key": "format",
        "text": "Какой формат материалов удобнее?",
        "buttons": [
            ("Видео + практика", "video_practice"),
            ("Статьи + практика", "articles"),
            ("Смешанный", "mixed"),
        ],
    },
]


def empty_session() -> dict:
    return {"step": 0, "answers": {}}


def current_question(session: dict) -> dict | None:
    step = session.get("step", 0)
    if step >= len(QUESTIONS):
        return None
    return QUESTIONS[step]


def accept_answer(session: dict, answer: str) -> bool:
    question = current_question(session)
    if not question:
        return False
    session["answers"][question["key"]] = answer.strip()
    session["step"] = session.get("step", 0) + 1
    return session["step"] >= len(QUESTIONS)
