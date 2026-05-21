import os

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .prompts import (
    COURSE_BUILDER_PROMPT,
    MATERIAL_STRUCTURING_PROMPT,
    TEXT_SEARCH_PROMPT,
    VIDEO_SEARCH_PROMPT,
)


def empty_list():
    return []


def empty_dict():
    return {}


def video_allowed_domains():
    return ["youtube.com", "rutube.ru", "vk.com", "vkvideo.ru"]


def text_allowed_domains():
    return ["stepik.org", "habr.com", "habr.ru", "practicum.yandex.ru", "htmlacademy.ru", "github.com"]


def default_agent_input():
    return "Найди подходящие учебные материалы для этого модуля."


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("создано", auto_now_add=True)
    updated_at = models.DateTimeField("обновлено", auto_now=True)

    class Meta:
        abstract = True


class LLMSettings(TimeStampedModel):
    class Provider(models.TextChoices):
        YANDEX = "yandex", "Yandex Cloud"
        OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible"
        OTHER = "other", "Другое"

    singleton_key = models.CharField(max_length=32, default="default", unique=True, editable=False)
    title = models.CharField("название", max_length=120, default="DEFAULT_LLM")
    is_active = models.BooleanField("активно", default=True)
    provider = models.CharField("провайдер", max_length=32, choices=Provider.choices, default=Provider.YANDEX)
    api_base_url = models.URLField("API base URL", blank=True)
    folder_id_env = models.CharField("env с folder id", max_length=120, default="YANDEX_CLOUD_FOLDER")
    api_key_env = models.CharField("env с API key", max_length=120, default="YANDEX_API_KEY")
    default_model = models.CharField("DEFAULT_LLM model", max_length=160, default="yandexgpt/latest")
    chat_provider = models.CharField(
        "DEFAULT_CHAT провайдер",
        max_length=32,
        choices=Provider.choices,
        default=Provider.OPENAI_COMPATIBLE,
    )
    chat_api_base_url = models.URLField("DEFAULT_CHAT API base URL", blank=True)
    chat_api_base_url_env = models.CharField(
        "env с DEFAULT_CHAT base URL",
        max_length=120,
        default="DEFAULT_LLM_BASE_URL",
    )
    chat_api_key_env = models.CharField(
        "env с DEFAULT_CHAT API key",
        max_length=120,
        default="DEFAULT_LLM_API_KEY",
    )
    default_chat_model = models.CharField("DEFAULT_CHAT_MODEL", max_length=160, default="gpt-4o-mini")
    temperature = models.DecimalField("temperature", max_digits=3, decimal_places=2, default=0.30)
    top_p = models.DecimalField("top_p", max_digits=3, decimal_places=2, default=0.90)
    max_output_tokens = models.PositiveIntegerField("max_output_tokens", default=1000)
    request_timeout_seconds = models.PositiveIntegerField("timeout, сек", default=60)
    course_builder_prompt = models.TextField("промпт построения курса", default=COURSE_BUILDER_PROMPT)
    material_structuring_prompt = models.TextField(
        "промпт структурирования материалов",
        default=MATERIAL_STRUCTURING_PROMPT,
    )
    response_format = models.JSONField("response_format / JSON schema", default=empty_dict, blank=True)
    extra_options = models.JSONField("дополнительные параметры", default=empty_dict, blank=True)

    class Meta:
        verbose_name = "DEFAULT_LLM"
        verbose_name_plural = "DEFAULT_LLM"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.singleton_key = "default"
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key="default")
        return obj

    def resolve_model_uri(self, model_name, provider=None):
        provider = provider or self.provider
        if provider == self.Provider.YANDEX:
            model_name = os.getenv("YANDEX_CLOUD_MODEL", "") or model_name
        if provider != self.Provider.YANDEX or model_name.startswith("gpt://"):
            return model_name
        folder_id = os.getenv(self.folder_id_env, "")
        if not folder_id:
            return model_name
        return f"gpt://{folder_id}/{model_name}"

    def resolve_chat_model_uri(self):
        env_model = os.getenv("DEFAULT_CHAT_MODEL", "")
        return self.resolve_model_uri(env_model or self.default_chat_model, provider=self.chat_provider)

    def api_base_url_for(self, purpose="default"):
        if purpose == "chat":
            return self.chat_api_base_url or os.getenv(self.chat_api_base_url_env, "")
        return self.api_base_url or os.getenv("WEB_SEARCH_BASE_URL", "")

    def api_key_env_for(self, purpose="default"):
        if purpose == "chat":
            return self.chat_api_key_env
        if not os.getenv(self.api_key_env, "") and os.getenv("WEB_SEARCH_API_KEY", ""):
            return "WEB_SEARCH_API_KEY"
        return self.api_key_env

    def provider_for(self, purpose="default"):
        if purpose == "chat":
            return self.chat_provider
        return self.provider


class WebSearchProfile(TimeStampedModel):
    class MaterialKind(models.TextChoices):
        VIDEO = "video", "Видео"
        TEXT = "text", "Текст и интерактив"

    class ContextSize(models.TextChoices):
        LOW = "low", "low"
        MEDIUM = "medium", "medium"
        HIGH = "high", "high"

    name = models.CharField("название", max_length=160)
    material_kind = models.CharField("тип материалов", max_length=16, choices=MaterialKind.choices)
    is_active = models.BooleanField("активно", default=True)
    prompt = models.TextField("промпт")
    allowed_domains = models.JSONField("allowed_domains", default=empty_list, blank=True)
    blocked_domains = models.JSONField("blocked_domains", default=empty_list, blank=True)
    search_context_size = models.CharField(
        "search_context_size",
        max_length=16,
        choices=ContextSize.choices,
        default=ContextSize.MEDIUM,
    )
    temperature = models.DecimalField("temperature", max_digits=3, decimal_places=2, default=0.30)
    max_output_tokens = models.PositiveIntegerField("max_output_tokens", default=1000)
    model_override = models.CharField("model override", max_length=160, blank=True)
    agent_prompt_id = models.CharField("Yandex prompt id", max_length=120, blank=True)
    agent_input = models.CharField("input для prompt-агента", max_length=300, default=default_agent_input, blank=True)
    tool_options = models.JSONField("дополнительные параметры tool", default=empty_dict, blank=True)

    class Meta:
        verbose_name = "WEB_SEARCH профиль"
        verbose_name_plural = "WEB_SEARCH профили"
        constraints = [
            models.UniqueConstraint(fields=["name", "material_kind"], name="unique_web_search_profile_name_kind")
        ]

    def __str__(self):
        return f"{self.name} ({self.get_material_kind_display()})"

    def build_responses_payload(self, llm_settings=None, variables=None):
        llm_settings = llm_settings or LLMSettings.get_solo()
        if self.agent_prompt_id:
            return {
                "prompt": {
                    "id": self.agent_prompt_id,
                    "variables": variables or {},
                },
                "input": self.agent_input or default_agent_input(),
                "max_output_tokens": self.max_output_tokens,
            }

        model = llm_settings.resolve_model_uri(self.model_override or llm_settings.default_model)
        tool = {
            "type": "web_search",
            "search_context_size": self.search_context_size,
        }
        filters = {}
        if self.allowed_domains:
            filters["allowed_domains"] = self.allowed_domains
        if self.blocked_domains:
            filters["blocked_domains"] = self.blocked_domains
        if filters:
            tool["filters"] = filters
        if self.tool_options:
            tool.update(self.tool_options)
        payload = {
            "model": model,
            "input": self.prompt,
            "tools": [tool],
            "temperature": float(self.temperature),
            "max_output_tokens": self.max_output_tokens,
        }
        return payload


class LearnerProfile(TimeStampedModel):
    user = models.OneToOneField(
        get_user_model(),
        verbose_name="пользователь",
        on_delete=models.CASCADE,
        related_name="learner_profile",
        null=True,
        blank=True,
    )
    telegram_id = models.CharField("Telegram ID", max_length=64, blank=True, db_index=True)
    display_name = models.CharField("имя", max_length=160, blank=True)
    city = models.CharField("город", max_length=120, blank=True)
    target_roles = models.JSONField("целевые роли/направления", default=empty_list, blank=True)
    competencies = models.JSONField("компетенции", default=empty_list, blank=True)
    learning_preferences = models.JSONField("предпочтения обучения", default=empty_dict, blank=True)
    notes = models.TextField("заметки", blank=True)

    class Meta:
        verbose_name = "профиль ученика"
        verbose_name_plural = "профили учеников"

    def __str__(self):
        return self.display_name or self.telegram_id or f"Профиль #{self.pk}"


class Course(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        BUILDING = "building", "Строится"
        READY = "ready", "Готов"
        IN_PROGRESS = "in_progress", "В процессе"
        COMPLETED = "completed", "Завершён"
        ARCHIVED = "archived", "Архив"

    learner = models.ForeignKey(
        LearnerProfile,
        verbose_name="ученик",
        on_delete=models.SET_NULL,
        related_name="courses",
        null=True,
        blank=True,
    )
    title = models.CharField("название", max_length=240)
    goal = models.TextField("цель пользователя")
    initial_level = models.CharField("исходный уровень", max_length=160, blank=True)
    target_level = models.CharField("целевой уровень", max_length=160, blank=True)
    status = models.CharField("статус", max_length=24, choices=Status.choices, default=Status.DRAFT)
    total_effort_hours = models.DecimalField("общая трудоёмкость, ч", max_digits=6, decimal_places=1, default=0)
    profile_snapshot = models.JSONField("снимок профиля", default=empty_dict, blank=True)
    recommendation_summary = models.TextField("объяснение рекомендаций", blank=True)
    pipeline_notes = models.TextField("заметки pipeline", blank=True)

    class Meta:
        verbose_name = "курс"
        verbose_name_plural = "курсы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class CourseModule(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирован"
        ACTIVE = "active", "Активен"
        SKIPPED = "skipped", "Пропущен"
        COMPLETED = "completed", "Завершён"
        NEEDS_ADJUSTMENT = "needs_adjustment", "Нужна корректировка"

    course = models.ForeignKey(Course, verbose_name="курс", on_delete=models.CASCADE, related_name="modules")
    title = models.CharField("название", max_length=240)
    order = models.PositiveIntegerField("порядок", default=1)
    description = models.TextField("описание")
    learning_outcomes = models.JSONField("результаты обучения", default=empty_list, blank=True)
    competencies = models.JSONField("приобретаемые компетенции", default=empty_list, blank=True)
    use_cases = models.TextField("где применяются навыки", blank=True)
    market_relevance = models.TextField("актуальность для вакансий/ролей", blank=True)
    total_effort_hours = models.DecimalField("трудоёмкость, ч", max_digits=6, decimal_places=1, default=0)
    status = models.CharField("статус", max_length=24, choices=Status.choices, default=Status.PLANNED)
    content_balance = models.CharField("баланс контента", max_length=120, default="Видео + текст + практика")
    adjustment_request = models.TextField("запрос на корректировку", blank=True)

    class Meta:
        verbose_name = "модуль курса"
        verbose_name_plural = "модули курса"
        ordering = ["course", "order"]
        constraints = [models.UniqueConstraint(fields=["course", "order"], name="unique_module_order_per_course")]

    def __str__(self):
        return f"{self.course}: {self.order}. {self.title}"


class LearningMaterial(TimeStampedModel):
    class Format(models.TextChoices):
        VIDEO = "video", "Видео"
        ARTICLE = "article", "Статья"
        DOCUMENTATION = "documentation", "Документация"
        ONLINE_COURSE = "online_course", "Онлайн-курс"
        INTERACTIVE = "interactive", "Интерактив"
        BOOK = "book", "Учебник/книга"
        EVENT = "event", "Мероприятие"
        REPOSITORY = "repository", "Репозиторий"
        OTHER = "other", "Другое"

    class Access(models.TextChoices):
        FREE = "free", "Бесплатно"
        OPEN = "open", "Открытый доступ"
        FREEMIUM = "freemium", "Частично бесплатно"
        UNKNOWN = "unknown", "Не проверено"

    title = models.CharField("название", max_length=300)
    url = models.URLField("URL", max_length=1000, unique=True)
    format = models.CharField("формат", max_length=32, choices=Format.choices)
    source = models.CharField("источник", max_length=160, blank=True)
    language = models.CharField("язык", max_length=32, default="ru")
    access = models.CharField("доступ", max_length=16, choices=Access.choices, default=Access.FREE)
    summary = models.TextField("краткое описание", blank=True)
    competencies = models.JSONField("компетенции", default=empty_list, blank=True)
    estimated_minutes = models.PositiveIntegerField("оценка времени, мин", default=0)
    quality_score = models.PositiveSmallIntegerField("оценка качества 0-100", default=0)
    is_active = models.BooleanField("использовать", default=True)
    metadata = models.JSONField("метаданные", default=empty_dict, blank=True)

    class Meta:
        verbose_name = "материал"
        verbose_name_plural = "материалы"
        ordering = ["title"]

    def __str__(self):
        return self.title


class ModuleElement(TimeStampedModel):
    class ElementType(models.TextChoices):
        THEORY = "theory", "Теория"
        THEORY_PRACTICE = "theory_practice", "Теория + практика"
        EVENT = "event", "Мероприятие"
        CHECKPOINT = "checkpoint", "Проверка результата"

    module = models.ForeignKey(CourseModule, verbose_name="модуль", on_delete=models.CASCADE, related_name="elements")
    material = models.ForeignKey(
        LearningMaterial,
        verbose_name="материал",
        on_delete=models.SET_NULL,
        related_name="module_elements",
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField("порядок", default=1)
    element_type = models.CharField("тип элемента", max_length=24, choices=ElementType.choices)
    title = models.CharField("название элемента", max_length=240)
    short_description = models.TextField("краткое описание", blank=True)
    acquired_competencies = models.JSONField("приобретаемые компетенции", default=empty_list, blank=True)
    estimated_minutes = models.PositiveIntegerField("оценка времени, мин", default=0)
    recommendation_reason = models.TextField("почему рекомендовано", blank=True)
    is_required = models.BooleanField("обязательно", default=True)
    calendar_reminder_at = models.DateTimeField("напоминание в календаре", null=True, blank=True)

    class Meta:
        verbose_name = "элемент модуля"
        verbose_name_plural = "элементы модулей"
        ordering = ["module", "order"]
        constraints = [models.UniqueConstraint(fields=["module", "order"], name="unique_element_order_per_module")]

    def __str__(self):
        return f"{self.module.title}: {self.order}. {self.title}"


class MaterialCandidate(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"
        DUPLICATE = "duplicate", "Дубликат"

    module = models.ForeignKey(
        CourseModule,
        verbose_name="модуль",
        on_delete=models.CASCADE,
        related_name="material_candidates",
        null=True,
        blank=True,
    )
    search_profile = models.ForeignKey(
        WebSearchProfile,
        verbose_name="профиль поиска",
        on_delete=models.SET_NULL,
        related_name="candidates",
        null=True,
        blank=True,
    )
    title = models.CharField("название", max_length=300)
    url = models.URLField("URL", max_length=1000)
    material_kind = models.CharField("тип", max_length=16, choices=WebSearchProfile.MaterialKind.choices)
    status = models.CharField("статус", max_length=16, choices=Status.choices, default=Status.NEW)
    rejection_reason = models.CharField("причина отклонения", max_length=240, blank=True)
    raw_payload = models.JSONField("сырой ответ поиска", default=empty_dict, blank=True)

    class Meta:
        verbose_name = "кандидат материала"
        verbose_name_plural = "кандидаты материалов"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["module", "url"], name="unique_candidate_url_per_module")]

    def __str__(self):
        return self.title


class MaterialFeedback(TimeStampedModel):
    class Rating(models.TextChoices):
        USEFUL = "useful", "Полезный"
        UNSUITABLE = "unsuitable", "Неподходящий"
        TOO_HARD = "too_hard", "Слишком сложный"
        TOO_EASY = "too_easy", "Слишком простой"

    learner = models.ForeignKey(
        LearnerProfile,
        verbose_name="ученик",
        on_delete=models.SET_NULL,
        related_name="material_feedback",
        null=True,
        blank=True,
    )
    element = models.ForeignKey(
        ModuleElement,
        verbose_name="элемент",
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    rating = models.CharField("оценка", max_length=24, choices=Rating.choices)
    comment = models.TextField("комментарий", blank=True)
    replacement_requested = models.BooleanField("нужна замена", default=False)
    replacement_kind = models.CharField(
        "заменить на тип",
        max_length=16,
        choices=WebSearchProfile.MaterialKind.choices,
        blank=True,
    )

    class Meta:
        verbose_name = "обратная связь по материалу"
        verbose_name_plural = "обратная связь по материалам"
        ordering = ["-created_at"]

    def clean(self):
        if self.rating in {self.Rating.UNSUITABLE, self.Rating.TOO_HARD, self.Rating.TOO_EASY}:
            self.replacement_requested = True

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.element} — {self.get_rating_display()}"


class Certificate(TimeStampedModel):
    learner = models.ForeignKey(
        LearnerProfile,
        verbose_name="ученик",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    element = models.ForeignKey(
        ModuleElement,
        verbose_name="элемент курса",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    title = models.CharField("название сертификата", max_length=240)
    issuer = models.CharField("организация", max_length=160, blank=True)
    issued_at = models.DateField("дата выдачи", null=True, blank=True)
    file = models.FileField("файл", upload_to="certificates/", blank=True)
    external_url = models.URLField("внешняя ссылка", blank=True)
    competencies = models.JSONField("подтверждённые компетенции", default=empty_list, blank=True)

    class Meta:
        verbose_name = "сертификат"
        verbose_name_plural = "сертификаты"
        ordering = ["-issued_at", "-created_at"]

    def __str__(self):
        return self.title


class PipelineRun(TimeStampedModel):
    class Step(models.TextChoices):
        PROFILE = "profile", "Сбор профиля"
        COURSE = "course", "Построение курса"
        VIDEO_SEARCH = "video_search", "Поиск видео"
        TEXT_SEARCH = "text_search", "Поиск текста"
        STRUCTURING = "structuring", "Структурирование"
        ADAPTATION = "adaptation", "Адаптация"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        RUNNING = "running", "Выполняется"
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"

    learner = models.ForeignKey(
        LearnerProfile,
        verbose_name="ученик",
        on_delete=models.SET_NULL,
        related_name="pipeline_runs",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        Course,
        verbose_name="курс",
        on_delete=models.SET_NULL,
        related_name="pipeline_runs",
        null=True,
        blank=True,
    )
    step = models.CharField("шаг", max_length=24, choices=Step.choices)
    status = models.CharField("статус", max_length=16, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField("начато", default=timezone.now)
    finished_at = models.DateTimeField("завершено", null=True, blank=True)
    input_payload = models.JSONField("вход", default=empty_dict, blank=True)
    output_payload = models.JSONField("выход", default=empty_dict, blank=True)
    error_message = models.TextField("ошибка", blank=True)

    class Meta:
        verbose_name = "запуск pipeline"
        verbose_name_plural = "запуски pipeline"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_step_display()} — {self.get_status_display()}"

    def mark_finished(self, status, output_payload=None, error_message=""):
        self.status = status
        self.finished_at = timezone.now()
        if output_payload is not None:
            self.output_payload = output_payload
        self.error_message = error_message
        self.save(update_fields=["status", "finished_at", "output_payload", "error_message", "updated_at"])
