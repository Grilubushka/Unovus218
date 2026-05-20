from django.contrib import admin, messages
from django.db.models import Count, Max
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Certificate,
    Course,
    CourseModule,
    LearnerProfile,
    LearningMaterial,
    LLMSettings,
    MaterialCandidate,
    MaterialFeedback,
    ModuleElement,
    PipelineRun,
    WebSearchProfile,
)


def dashboard_callback(request, context):
    context.update(
        {
            "kpi": {
                "courses": Course.objects.count(),
                "ready_courses": Course.objects.filter(status=Course.Status.READY).count(),
                "materials": LearningMaterial.objects.filter(is_active=True).count(),
                "feedback_to_replace": MaterialFeedback.objects.filter(replacement_requested=True).count(),
            }
        }
    )
    return context


class CourseModuleInline(TabularInline):
    model = CourseModule
    extra = 0
    fields = ("order", "title", "status", "total_effort_hours", "content_balance")
    show_change_link = True


class ModuleElementInline(TabularInline):
    model = ModuleElement
    extra = 0
    autocomplete_fields = ("material",)
    fields = ("order", "element_type", "title", "material", "estimated_minutes", "is_required")
    show_change_link = True


class CertificateInline(TabularInline):
    model = Certificate
    extra = 0
    fields = ("title", "issuer", "issued_at", "external_url", "file")
    show_change_link = True


@admin.register(LLMSettings)
class LLMSettingsAdmin(ModelAdmin):
    list_display = (
        "title",
        "provider",
        "default_model",
        "chat_provider",
        "default_chat_model",
        "temperature",
        "max_output_tokens",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Основное", {"fields": ("title", "is_active")}),
        (
            "DEFAULT_LLM: web_search и структурирование",
            {"fields": ("provider", "api_base_url", "folder_id_env", "api_key_env", "default_model")},
        ),
        (
            "DEFAULT_CHAT: уточнения и построение курса",
            {
                "fields": (
                    "chat_provider",
                    "chat_api_base_url",
                    "chat_api_base_url_env",
                    "chat_api_key_env",
                    "default_chat_model",
                )
            },
        ),
        (
            "Общие параметры генерации",
            {
                "fields": (
                    "temperature",
                    "top_p",
                    "max_output_tokens",
                    "request_timeout_seconds",
                    "response_format",
                    "extra_options",
                )
            },
        ),
        ("Промпты pipeline", {"fields": ("course_builder_prompt", "material_structuring_prompt")}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return not LLMSettings.objects.exists()


@admin.register(WebSearchProfile)
class WebSearchProfileAdmin(ModelAdmin):
    list_display = (
        "name",
        "material_kind",
        "is_active",
        "agent_prompt_id",
        "search_context_size",
        "temperature",
        "max_output_tokens",
        "domain_count",
    )
    list_filter = ("material_kind", "is_active", "search_context_size")
    search_fields = ("name", "prompt", "agent_prompt_id", "allowed_domains")
    readonly_fields = ("created_at", "updated_at", "payload_preview")
    fieldsets = (
        ("Назначение", {"fields": ("name", "material_kind", "is_active")}),
        ("Yandex prompt-агент", {"fields": ("agent_prompt_id", "agent_input")}),
        ("Локальный промпт fallback", {"classes": ("collapse",), "fields": ("prompt",)}),
        (
            "Web Search параметры",
            {
                "fields": (
                    "allowed_domains",
                    "blocked_domains",
                    "search_context_size",
                    "temperature",
                    "max_output_tokens",
                    "model_override",
                    "tool_options",
                )
            },
        ),
        ("Предпросмотр Responses API", {"classes": ("collapse",), "fields": ("payload_preview",)}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="доменов")
    def domain_count(self, obj):
        return len(obj.allowed_domains or [])

    @admin.display(description="payload")
    def payload_preview(self, obj):
        if not obj.pk:
            return "Сохраните профиль, чтобы увидеть payload."
        return obj.build_responses_payload()


@admin.register(LearnerProfile)
class LearnerProfileAdmin(ModelAdmin):
    list_display = ("display_name", "telegram_id", "city", "course_count", "created_at")
    search_fields = ("display_name", "telegram_id", "city", "notes")
    readonly_fields = ("created_at", "updated_at")
    inlines = (CertificateInline,)
    fieldsets = (
        ("Идентификация", {"fields": ("user", "telegram_id", "display_name", "city")}),
        ("Портфолио", {"fields": ("competencies", "target_roles", "learning_preferences")}),
        ("Заметки", {"fields": ("notes",)}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="курсов")
    def course_count(self, obj):
        return obj.courses.count()


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ("title", "learner", "status", "total_effort_hours", "module_count", "element_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "goal", "initial_level", "target_level", "recommendation_summary")
    autocomplete_fields = ("learner",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (CourseModuleInline,)
    fieldsets = (
        ("Курс", {"fields": ("title", "learner", "status", "goal")}),
        ("Персонализация", {"fields": ("initial_level", "target_level", "profile_snapshot")}),
        ("Трудоёмкость и объяснение", {"fields": ("total_effort_hours", "recommendation_summary", "pipeline_notes")}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("learner")
            .annotate(module_total=Count("modules", distinct=True), element_total=Count("modules__elements", distinct=True))
        )

    @admin.display(description="модулей", ordering="module_total")
    def module_count(self, obj):
        return obj.module_total

    @admin.display(description="элементов", ordering="element_total")
    def element_count(self, obj):
        return obj.element_total


@admin.register(CourseModule)
class CourseModuleAdmin(ModelAdmin):
    list_display = ("title", "course", "order", "status", "total_effort_hours", "element_count", "candidate_count")
    list_filter = ("status", "course__status")
    search_fields = ("title", "description", "use_cases", "market_relevance", "course__title", "course__goal")
    autocomplete_fields = ("course",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ModuleElementInline,)
    actions = ("mark_skipped", "mark_needs_adjustment")
    fieldsets = (
        ("Модуль", {"fields": ("course", "order", "title", "status", "description")}),
        (
            "Польза и результат",
            {"fields": ("learning_outcomes", "competencies", "use_cases", "market_relevance", "total_effort_hours")},
        ),
        ("Адаптация", {"fields": ("content_balance", "adjustment_request")}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("course")
            .annotate(element_total=Count("elements", distinct=True), candidate_total=Count("material_candidates", distinct=True))
        )

    @admin.display(description="элементов", ordering="element_total")
    def element_count(self, obj):
        return obj.element_total

    @admin.display(description="кандидатов", ordering="candidate_total")
    def candidate_count(self, obj):
        return obj.candidate_total

    @admin.action(description="Пропустить модуль")
    def mark_skipped(self, request, queryset):
        updated = queryset.update(status=CourseModule.Status.SKIPPED)
        self.message_user(request, f"Модулей пропущено: {updated}.", messages.SUCCESS)

    @admin.action(description="Запросить корректировку")
    def mark_needs_adjustment(self, request, queryset):
        updated = queryset.update(status=CourseModule.Status.NEEDS_ADJUSTMENT)
        self.message_user(request, f"Модулей отправлено на корректировку: {updated}.", messages.SUCCESS)


@admin.register(LearningMaterial)
class LearningMaterialAdmin(ModelAdmin):
    list_display = ("title", "format", "source", "access", "estimated_minutes", "quality_score", "is_active", "open_url")
    list_filter = ("format", "access", "language", "is_active")
    search_fields = ("title", "url", "source", "summary", "competencies")
    readonly_fields = ("created_at", "updated_at", "open_url")
    fieldsets = (
        ("Материал", {"fields": ("title", "url", "open_url", "format", "source", "language", "access", "is_active")}),
        ("Учебная ценность", {"fields": ("summary", "competencies", "estimated_minutes", "quality_score")}),
        ("Метаданные", {"classes": ("collapse",), "fields": ("metadata", "created_at", "updated_at")}),
    )

    @admin.display(description="ссылка")
    def open_url(self, obj):
        if not obj.url:
            return ""
        return format_html('<a href="{}" target="_blank" rel="noopener">открыть</a>', obj.url)


@admin.register(ModuleElement)
class ModuleElementAdmin(ModelAdmin):
    list_display = ("title", "module", "order", "element_type", "material", "estimated_minutes", "is_required")
    list_filter = ("element_type", "is_required", "module__course__status")
    search_fields = ("title", "short_description", "recommendation_reason", "module__title", "material__title")
    autocomplete_fields = ("module", "material")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Элемент", {"fields": ("module", "order", "title", "element_type", "material", "is_required")}),
        (
            "Описание",
            {"fields": ("short_description", "estimated_minutes", "acquired_competencies", "recommendation_reason")},
        ),
        ("Опциональные действия", {"fields": ("calendar_reminder_at",)}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )


@admin.register(MaterialCandidate)
class MaterialCandidateAdmin(ModelAdmin):
    list_display = ("title", "material_kind", "status", "module", "search_profile", "open_url", "created_at")
    list_filter = ("material_kind", "status", "search_profile")
    search_fields = ("title", "url", "module__title", "module__course__goal")
    autocomplete_fields = ("module", "search_profile")
    readonly_fields = ("created_at", "updated_at", "open_url")
    actions = ("accept_as_material", "reject_candidates", "mark_duplicates")
    fieldsets = (
        ("Кандидат", {"fields": ("title", "url", "open_url", "material_kind", "status", "rejection_reason")}),
        ("Контекст поиска", {"fields": ("module", "search_profile", "raw_payload")}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="ссылка")
    def open_url(self, obj):
        if not obj.url:
            return ""
        return format_html('<a href="{}" target="_blank" rel="noopener">открыть</a>', obj.url)

    @admin.action(description="Принять как материал")
    def accept_as_material(self, request, queryset):
        created = 0
        for candidate in queryset:
            material_format = (
                LearningMaterial.Format.VIDEO
                if candidate.material_kind == WebSearchProfile.MaterialKind.VIDEO
                else LearningMaterial.Format.ARTICLE
            )
            material, was_created = LearningMaterial.objects.get_or_create(
                url=candidate.url,
                defaults={
                    "title": candidate.title,
                    "format": material_format,
                    "summary": f"Материал найден для модуля: {candidate.module.title}" if candidate.module else "",
                },
            )
            candidate.status = MaterialCandidate.Status.ACCEPTED
            candidate.save(update_fields=["status", "updated_at"])
            if was_created:
                created += 1
            if candidate.module:
                next_order = (candidate.module.elements.aggregate(last_order=Max("order"))["last_order"] or 0) + 1
                ModuleElement.objects.get_or_create(
                    module=candidate.module,
                    material=material,
                    defaults={
                        "order": next_order,
                        "title": candidate.title[:240],
                        "element_type": ModuleElement.ElementType.THEORY,
                        "short_description": "Добавлено из кандидатов Web Search.",
                    },
                )
        self.message_user(request, f"Создано новых материалов: {created}.", messages.SUCCESS)

    @admin.action(description="Отклонить")
    def reject_candidates(self, request, queryset):
        updated = queryset.update(status=MaterialCandidate.Status.REJECTED)
        self.message_user(request, f"Кандидатов отклонено: {updated}.", messages.SUCCESS)

    @admin.action(description="Пометить как дубликаты")
    def mark_duplicates(self, request, queryset):
        updated = queryset.update(status=MaterialCandidate.Status.DUPLICATE)
        self.message_user(request, f"Дубликатов помечено: {updated}.", messages.SUCCESS)


@admin.register(MaterialFeedback)
class MaterialFeedbackAdmin(ModelAdmin):
    list_display = ("element", "learner", "rating", "replacement_requested", "replacement_kind", "created_at")
    list_filter = ("rating", "replacement_requested", "replacement_kind")
    search_fields = ("comment", "element__title", "element__material__title", "learner__display_name")
    autocomplete_fields = ("learner", "element")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Certificate)
class CertificateAdmin(ModelAdmin):
    list_display = ("title", "learner", "issuer", "issued_at", "element", "created_at")
    list_filter = ("issuer", "issued_at")
    search_fields = ("title", "issuer", "learner__display_name", "competencies")
    autocomplete_fields = ("learner", "element")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PipelineRun)
class PipelineRunAdmin(ModelAdmin):
    list_display = ("step", "status", "learner", "course", "started_at", "finished_at")
    list_filter = ("step", "status", "started_at")
    search_fields = ("learner__display_name", "course__title", "error_message")
    autocomplete_fields = ("learner", "course")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at")
    fieldsets = (
        ("Запуск", {"fields": ("learner", "course", "step", "status", "started_at", "finished_at")}),
        ("Данные", {"fields": ("input_payload", "output_payload", "error_message")}),
        ("Служебное", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )
