from bot.domain.roadmap import UserProfile


def profile_from_answers(answers: dict) -> UserProfile:
    return UserProfile(
        goal=answers.get("goal", "Хочу освоить новый навык"),
        direction=answers.get("direction", "programming"),
        age=answers.get("age", "16"),
        result=answers.get("result", "project"),
        experience=answers.get("experience", "none"),
        weekly_time=answers.get("weekly_time", "4"),
        motivation=answers.get("motivation", "try"),
        format=answers.get("format", "video_practice"),
    )


def roadmap_message(roadmap: dict) -> str:
    lines = [
        f"Твой маршрут готов: «{roadmap['track']}»",
        "",
        f"Направление: {roadmap['domain']}",
        f"Тем: {roadmap['total_topics']}",
        f"Срок: {roadmap['duration']}",
        f"Результат: {roadmap['result']}",
        "",
        roadmap["explanation"],
        "",
        "Первые шаги:",
    ]
    for index, module in enumerate(roadmap["modules"], start=1):
        topics = ", ".join(topic["title"] for topic in module["topics"][:4])
        lines.append(f"{index}. {module['title']} — {module['goal']}. Темы: {topics}.")
    return "\n".join(lines)


def topic_message(roadmap: dict) -> str:
    topic = roadmap["modules"][0]["topics"][0]
    materials = "\n".join(f"- {material}" for material in topic["materials"])
    skills = ", ".join(topic["skills"])
    return (
        f"Текущая тема: {topic['title']}\n\n"
        f"Навыки: {skills}\n\n"
        f"Материалы:\n{materials}\n\n"
        "Можно отметить прогресс или попросить замену материала."
    )
