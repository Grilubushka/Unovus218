"""
skills_extractor.py — извлечение навыков из описания вакансии.

Два подхода:
  1. Секционный парсинг — находит разделы "Требования:", "Навыки:", "Что нужно знать:" и берёт пункты.
  2. Словарный матчинг — сканирует текст на совпадение с базой ~300 навыков.

Результат: список уникальных навыков (строк).
"""

import re
from typing import List, Set

# ── Большая база навыков ───────────────────────────────────────────────────────
# Ключ — категория (для информации), значение — список вариантов написания

SKILLS_DB = {
    # ── Языки программирования ──────────────────────────────────────────────
    "languages": [
        "Python", "Java", "JavaScript", "TypeScript", "C\\+\\+", "C#", "Go",
        "Golang", "Rust", "Swift", "Kotlin", "PHP", "Ruby", "Scala", "R",
        "Perl", "Dart", "Lua", "MATLAB", "Groovy", "Elixir", "Haskell",
        "1С", "1С:Предприятие",
    ],
    # ── Веб и фреймворки ────────────────────────────────────────────────────
    "web": [
        "React", "Vue\\.js", "Angular", "Next\\.js", "Nuxt\\.js", "Svelte",
        "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Laravel",
        "Node\\.js", "Express", "NestJS", "ASP\\.NET", "Ruby on Rails",
        "jQuery", "Bootstrap", "Tailwind", "GraphQL", "REST API", "gRPC",
        "WebSocket", "Webpack", "Vite", "HTML", "CSS", "SCSS", "LESS",
    ],
    # ── Базы данных ─────────────────────────────────────────────────────────
    "databases": [
        "SQL", "PostgreSQL", "MySQL", "SQLite", "Oracle", "MS SQL",
        "MongoDB", "Redis", "Elasticsearch", "Cassandra", "ClickHouse",
        "DynamoDB", "Firebase", "Supabase", "Prisma", "Hibernate",
        "SQLAlchemy",
    ],
    # ── DevOps / инфраструктура ─────────────────────────────────────────────
    "devops": [
        "Docker", "Kubernetes", "Helm", "Terraform", "Ansible", "Jenkins",
        "GitLab CI", "GitHub Actions", "CircleCI", "CI/CD", "Linux",
        "Nginx", "Apache", "AWS", "Azure", "GCP", "Yandex Cloud",
        "Prometheus", "Grafana", "ELK", "Kafka", "RabbitMQ", "Celery",
    ],
    # ── Инструменты разработки ──────────────────────────────────────────────
    "tools": [
        "Git", "Jira", "Confluence", "Bitbucket", "GitHub", "GitLab",
        "Postman", "Swagger", "VS Code", "IntelliJ", "PyCharm", "Vim",
        "Linux", "Bash", "Shell", "PowerShell", "Makefile",
    ],
    # ── Данные и ML ─────────────────────────────────────────────────────────
    "data_ml": [
        "Machine Learning", "Deep Learning", "Pandas", "NumPy", "Scikit-learn",
        "TensorFlow", "PyTorch", "Keras", "Spark", "Hadoop", "Airflow",
        "dbt", "Power BI", "Tableau", "Looker", "Excel", "Google Sheets",
        "A/B тест", "A/B тестирование", "статистика", "аналитика",
        "Data Science", "NLP", "Computer Vision",
    ],
    # ── Офисное ПО ──────────────────────────────────────────────────────────
    "office": [
        "Microsoft Office", "Word", "PowerPoint", "Outlook", "Access",
        "1С:Бухгалтерия", "1С:ЗУП", "SAP", "Bitrix24", "AmoCRM",
        "Salesforce", "HubSpot", "Trello", "Asana", "Notion",
    ],
    # ── Маркетинг ───────────────────────────────────────────────────────────
    "marketing": [
        "SEO", "SEM", "SMM", "контекстная реклама", "таргетинг",
        "Яндекс.Директ", "Google Ads", "Facebook Ads", "ВКонтакте реклама",
        "email-маркетинг", "контент-маркетинг", "копирайтинг",
        "Google Analytics", "Яндекс.Метрика", "CRM",
        "воронка продаж", "лидогенерация",
    ],
    # ── Продажи ─────────────────────────────────────────────────────────────
    "sales": [
        "холодные звонки", "активные продажи", "B2B", "B2C",
        "ведение переговоров", "переговоры", "работа с возражениями",
        "KPI", "план продаж", "CRM", "документооборот",
        "деловая переписка", "тендер", "торги",
    ],
    # ── Управление / менеджмент ──────────────────────────────────────────────
    "management": [
        "Agile", "Scrum", "Kanban", "PRINCE2", "PMI", "управление проектами",
        "product management", "product owner", "управление командой",
        "стратегическое планирование", "бюджетирование", "OKR",
        "управление рисками",
    ],
    # ── Финансы / бухгалтерия ────────────────────────────────────────────────
    "finance": [
        "бухгалтерский учёт", "налоговый учёт", "МСФО", "РСБУ",
        "финансовый анализ", "финансовое планирование", "бюджетирование",
        "казначейство", "аудит", "IFRS", "управленческий учёт",
    ],
    # ── HR ──────────────────────────────────────────────────────────────────
    "hr": [
        "рекрутинг", "подбор персонала", "HR", "кадровое делопроизводство",
        "трудовое законодательство", "onboarding", "адаптация персонала",
        "оценка персонала", "мотивация", "корпоративная культура",
    ],
    # ── Soft skills ─────────────────────────────────────────────────────────
    "soft": [
        "командная работа", "работа в команде", "коммуникабельность",
        "многозадачность", "стрессоустойчивость", "самостоятельность",
        "ответственность", "внимательность", "обучаемость",
        "аналитическое мышление", "системное мышление", "лидерство",
        "тайм-менеджмент", "клиентоориентированность",
    ],
    # ── Языки ───────────────────────────────────────────────────────────────
    "spoken_lang": [
        "английский язык", "английский", "немецкий язык", "немецкий",
        "китайский язык", "французский язык", "испанский язык",
        "английский B1", "английский B2", "английский C1",
        "Upper-Intermediate", "Intermediate", "Advanced",
    ],
    # ── Логистика / склад ────────────────────────────────────────────────────
    "logistics": [
        "1С:Склад", "WMS", "TMS", "управление запасами", "инвентаризация",
        "таможенное оформление", "ВЭД", "логистика", "цепочка поставок",
    ],
    # ── Юридическое ─────────────────────────────────────────────────────────
    "legal": [
        "договорная работа", "корпоративное право", "арбитраж",
        "трудовое право", "гражданское право", "составление договоров",
        "правовая экспертиза", "судебная практика",
    ],
}

# Строим плоский список паттернов с флагом IGNORECASE
_PATTERNS: List[re.Pattern] = []
_SKILL_NAMES: List[str] = []

for category, skills in SKILLS_DB.items():
    for skill in skills:
        # Для каждого навыка — паттерн на границе слова
        try:
            pat = re.compile(r"\b" + skill + r"\b", re.IGNORECASE | re.UNICODE)
            _PATTERNS.append(pat)
            # Сохраняем "красивое" имя (убираем экранирование regex)
            clean = skill.replace("\\.", ".").replace("\\+", "+").replace("\\ ", " ")
            _SKILL_NAMES.append(clean)
        except re.error:
            pass  # Пропускаем невалидные паттерны


# ── Паттерны разделов с требованиями ──────────────────────────────────────────

_SECTION_HEADERS = re.compile(
    r"(?:требования|что нужно знать|что нам важно|необходимые навыки|"
    r"навыки и опыт|ожидаем|ожидания|стек|технологии|what we expect|"
    r"что мы ждём|hard skills|наши ожидания|вы умеете|от вас ждём|"
    r"квалификация|пожелания к кандидату|что нужно|от кандидата|"
    r"обязательные требования|ключевые навыки)\s*:?",
    re.IGNORECASE | re.UNICODE,
)

_SECTION_END = re.compile(
    r"(?:будет плюсом|nice to have|мы предлагаем|условия|что мы предлагаем|"
    r"задачи|обязанности|о компании|о нас|вакансия|должностные)",
    re.IGNORECASE | re.UNICODE,
)

_BULLET = re.compile(
    r"^\s*[-•·▪*✓✔►→]\s*(.+)$|^\s*\d+[.)]\s*(.+)$",
    re.MULTILINE,
)


def _extract_section_skills(text: str) -> List[str]:
    """Вытащить пункты из разделов с требованиями."""
    skills: List[str] = []
    lines = text.splitlines()
    in_section = False

    for line in lines:
        stripped = line.strip()
        if _SECTION_HEADERS.search(stripped):
            in_section = True
            continue
        if in_section:
            if _SECTION_END.search(stripped) and stripped:
                in_section = False
                continue
            # Пункт списка
            m = _BULLET.match(line)
            if m:
                item = (m.group(1) or m.group(2) or "").strip()
                if item and len(item) > 2:
                    skills.append(item)
            # Или просто непустая строка в разделе (без маркера)
            elif stripped and 5 < len(stripped) < 200:
                skills.append(stripped)

    return skills


def _extract_vocab_skills(text: str) -> Set[str]:
    """Поиск навыков из словаря."""
    found: Set[str] = set()
    for pattern, name in zip(_PATTERNS, _SKILL_NAMES):
        if pattern.search(text):
            found.add(name)
    return found


def extract_skills(description: str) -> List[str]:
    """
    Главная функция извлечения навыков из описания вакансии.

    Порядок:
    1. Ищет секцию 'Требования' и вытаскивает пункты списка.
    2. Дополнительно сканирует весь текст по словарю навыков.
    3. Объединяет, убирает дубли, сортирует.
    """
    if not description:
        return []

    section_items = _extract_section_skills(description)
    vocab_hits    = _extract_vocab_skills(description)

    # Объединяем: сначала пункты из секции, потом словарные hits которых нет в секции
    section_text = " ".join(section_items).lower()
    extra_vocab = [s for s in vocab_hits if s.lower() not in section_text]

    combined = section_items + sorted(extra_vocab)

    # Убираем дубли, сохраняя порядок
    seen: Set[str] = set()
    unique: List[str] = []
    for item in combined:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())

    return unique
