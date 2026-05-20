from dataclasses import dataclass

from .catalog import DOMAINS, MATERIALS


@dataclass(frozen=True)
class UserProfile:
    goal: str
    direction: str
    age: str
    result: str
    experience: str
    weekly_time: str
    motivation: str
    format: str


def build_roadmap(profile: UserProfile) -> dict:
    domain_key = _pick_domain(profile)
    track_key = _pick_track(domain_key, profile)
    domain = DOMAINS[domain_key]
    track = domain["tracks"][track_key]
    route_mode = _pick_route_mode(profile)
    module_limit = 3 if route_mode != "career" else 4
    topic_limit = 10 if route_mode == "supportive" else 12

    modules = []
    total_topics = 0
    for module in track["modules"][:module_limit]:
        topics = module["topics"][: max(topic_limit - total_topics, 0)]
        if not topics:
            break
        total_topics += len(topics)
        modules.append(
            {
                "title": module["title"],
                "goal": module["goal"],
                "topics": [
                    {
                        "title": topic,
                        "skills": _skills_for(topic),
                        "materials": _materials_for(profile.format),
                    }
                    for topic in topics
                ],
            }
        )

    return {
        "domain": domain["title"],
        "track": track["title"],
        "duration": track["duration"],
        "result": track["result"],
        "route_mode": route_mode,
        "modules": modules,
        "total_topics": total_topics,
        "explanation": _explain(profile, track, route_mode),
    }


def _pick_domain(profile: UserProfile) -> str:
    text = f"{profile.goal} {profile.direction} {profile.result}".lower()
    if profile.direction == "english" or "англ" in text or "поезд" in text:
        return "english"
    if profile.direction == "cooking" or "готов" in text or "кулин" in text or "ужин" in text:
        return "cooking"
    return "programming"


def _pick_track(domain_key: str, profile: UserProfile) -> str:
    text = f"{profile.goal} {profile.result}".lower()
    if domain_key == "programming" and ("сайт" in text or "frontend" in text):
        return "frontend-zero"
    if domain_key == "english":
        return "english-travel"
    if domain_key == "cooking":
        return "home-dinners"
    return "python-zero"


def _pick_route_mode(profile: UserProfile) -> str:
    if profile.motivation == "career":
        return "career"
    if profile.motivation == "support" or _safe_int(profile.weekly_time) <= 2:
        return "supportive"
    if profile.result == "try_fast":
        return "quick_start"
    return "balanced"


def _materials_for(preferred_format: str) -> list[str]:
    if preferred_format == "video_practice":
        keys = ["video", "practice", "quiz"]
    elif preferred_format == "articles":
        keys = ["article", "practice", "quiz"]
    else:
        keys = ["video", "article", "practice"]
    return [MATERIALS[key] for key in keys]


def _skills_for(topic: str) -> list[str]:
    mapping = {
        "Переменные": ["хранение значений", "вывод данных"],
        "Циклы": ["for", "while", "повторение действий"],
        "Аэропорт": ["регистрация", "багаж", "поиск выхода"],
        "Крупа и белок": ["гарнир", "белок", "баланс блюда"],
    }
    return mapping.get(topic, ["базовое понимание", "практическое применение"])


def _explain(profile: UserProfile, track: dict, route_mode: str) -> str:
    mode_text = {
        "quick_start": "короткий быстрый старт",
        "balanced": "сбалансированный маршрут",
        "career": "маршрут с карьерным уклоном",
        "supportive": "мягкий маршрут маленькими шагами",
    }[route_mode]
    return (
        f"Я выбрал «{track['title']}» как {mode_text}: учитываю возраст {profile.age}, "
        f"опыт «{profile.experience}», {profile.weekly_time} ч/нед. и формат материалов."
    )


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 4
