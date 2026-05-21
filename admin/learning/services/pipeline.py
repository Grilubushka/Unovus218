from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlparse

from django.db import transaction

from learning.models import (
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
from learning.prompts import PROFILE_QUESTIONS_PROMPT
from learning.services.llm import LLMResponseError, ResponsesLLMClient


MAX_GOAL_CHARS = 1200
MAX_PROFILE_SNAPSHOT_CHARS = 2000
MAX_MODULE_FIELD_CHARS = 700
MAX_REJECTED_URLS = 20
MAX_CANDIDATES_FOR_STRUCTURING = 6


@dataclass(frozen=True)
class UserGoal:
    goal: str
    current_level: str = ""
    target_level: str = ""
    weekly_hours: int | None = None
    preferred_formats: list[str] | None = None
    constraints: dict | None = None


class CoursePipeline:
    """Orchestrates the learning route flow used by the bot and mini app."""

    def __init__(self, llm_settings=None, llm_client=None):
        self.llm_settings = llm_settings or LLMSettings.get_solo()
        self.llm_client = llm_client or ResponsesLLMClient(self.llm_settings)

    def ask_profile_questions(self, goal: str) -> list[dict]:
        prompt = "\n\n".join([PROFILE_QUESTIONS_PROMPT, f"Цель пользователя: {goal}"])
        payload = self._base_llm_payload(
            prompt,
            model=self.llm_settings.resolve_chat_model_uri(),
        )
        payload["max_output_tokens"] = min(self.llm_settings.max_output_tokens, 700)
        data = self.llm_client.create_json(payload, purpose="chat")
        questions = self._extract_list_response(data, "questions")
        return [question for question in questions if question.get("text")][:3]

    @transaction.atomic
    def create_course_draft(self, learner: LearnerProfile | None, user_goal: UserGoal) -> Course:
        run = PipelineRun.objects.create(
            learner=learner,
            step=PipelineRun.Step.PROFILE,
            status=PipelineRun.Status.RUNNING,
            input_payload={
                "goal": user_goal.goal,
                "current_level": user_goal.current_level,
                "target_level": user_goal.target_level,
                "weekly_hours": user_goal.weekly_hours,
                "preferred_formats": user_goal.preferred_formats or [],
                "constraints": user_goal.constraints or {},
            },
        )
        course = Course.objects.create(
            learner=learner,
            title=user_goal.goal[:240],
            goal=user_goal.goal,
            initial_level=user_goal.current_level,
            target_level=user_goal.target_level,
            status=Course.Status.DRAFT,
            profile_snapshot=run.input_payload,
        )
        run.course = course
        run.save(update_fields=["course", "updated_at"])
        run.mark_finished(PipelineRun.Status.SUCCESS, {"course_id": course.id})
        return course

    def build_course_request(self, course: Course) -> dict:
        prompt = "\n\n".join(
            [
                self.llm_settings.course_builder_prompt,
                f"Цель пользователя: {self._truncate(course.goal, MAX_GOAL_CHARS)}",
                f"Исходный уровень: {self._truncate(course.initial_level or 'не указан', 300)}",
                f"Целевой уровень: {self._truncate(course.target_level or 'не указан', 300)}",
                f"Снимок профиля: {self._compact_json(course.profile_snapshot, MAX_PROFILE_SNAPSHOT_CHARS)}",
            ]
        )
        return self._base_llm_payload(prompt, model=self.llm_settings.resolve_chat_model_uri())

    def build_course_from_goal(self, learner: LearnerProfile | None, user_goal: UserGoal) -> Course:
        course = self.create_course_draft(learner, user_goal)
        try:
            course.status = Course.Status.BUILDING
            course.save(update_fields=["status", "updated_at"])
            course_data = self.generate_course_outline(course)
            self.apply_course_outline(course, course_data)
            if not course.modules.exists():
                raise LLMResponseError("LLM не вернула модули курса в ожидаемой схеме.")
            self.activate_first_module(course)
            for module in course.modules.order_by("order"):
                self.search_module_materials(module, WebSearchProfile.MaterialKind.VIDEO)
                self.search_module_materials(module, WebSearchProfile.MaterialKind.TEXT)
                self.structure_module_materials(module)
            course.status = Course.Status.READY
            course.save(update_fields=["status", "updated_at"])
            return course
        except Exception as exc:
            course.status = Course.Status.DRAFT
            course.pipeline_notes = str(exc)
            course.save(update_fields=["status", "pipeline_notes", "updated_at"])
            raise

    def generate_course_outline(self, course: Course) -> dict:
        run = PipelineRun.objects.create(
            learner=course.learner,
            course=course,
            step=PipelineRun.Step.COURSE,
            status=PipelineRun.Status.RUNNING,
            input_payload={"course_id": course.id, "goal": course.goal, "profile": course.profile_snapshot},
        )
        try:
            payload = self.build_course_request(course)
            data = self.llm_client.create_json(payload, purpose="chat")
            data = self._normalize_object_response(data, "course")
            run.mark_finished(PipelineRun.Status.SUCCESS, data)
            return data
        except Exception as exc:
            run.mark_finished(PipelineRun.Status.FAILED, error_message=str(exc))
            raise

    @transaction.atomic
    def apply_course_outline(self, course: Course, data: dict) -> None:
        course.title = str(data.get("title") or course.title)[:240]
        course.initial_level = str(data.get("initial_level") or course.initial_level)[:160]
        course.target_level = str(data.get("target_level") or course.target_level)[:160]
        course.total_effort_hours = self._decimal(data.get("total_effort_hours"))
        course.recommendation_summary = str(data.get("recommendation_summary") or "")
        course.save(
            update_fields=[
                "title",
                "initial_level",
                "target_level",
                "total_effort_hours",
                "recommendation_summary",
                "updated_at",
            ]
        )
        course.modules.all().delete()
        for index, module_data in enumerate(data.get("modules") or [], start=1):
            CourseModule.objects.create(
                course=course,
                order=index,
                title=str(module_data.get("title") or f"Модуль {index}")[:240],
                description=str(module_data.get("description") or ""),
                learning_outcomes=self._list(module_data.get("learning_outcomes")),
                competencies=self._list(module_data.get("competencies")),
                use_cases=str(module_data.get("use_cases") or ""),
                market_relevance=str(module_data.get("market_relevance") or ""),
                total_effort_hours=self._decimal(module_data.get("total_effort_hours")),
                content_balance=str(module_data.get("content_balance") or "Видео + текст + практика")[:120],
            )

    def activate_first_module(self, course: Course) -> None:
        if course.modules.exclude(status=CourseModule.Status.PLANNED).exists():
            return
        first_module = course.modules.order_by("order").first()
        if first_module:
            first_module.status = CourseModule.Status.ACTIVE
            first_module.save(update_fields=["status", "updated_at"])

    def build_material_search_request(
        self,
        module: CourseModule,
        material_kind: str,
        rejected_urls: list[str] | None = None,
    ) -> dict:
        profile = (
            WebSearchProfile.objects.filter(material_kind=material_kind, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if profile is None:
            raise WebSearchProfile.DoesNotExist(f"No active Web Search profile for {material_kind}")

        rejected_urls = (rejected_urls or [])[:MAX_REJECTED_URLS]
        variables = {
            "course_goal": self._truncate(module.course.goal, MAX_GOAL_CHARS),
            "module": self._module_context(module, compact=True),
            "rejected_urls": "\n".join(rejected_urls) or "[]",
        }
        payload = profile.build_responses_payload(self.llm_settings, variables=variables)
        payload["max_output_tokens"] = min(payload.get("max_output_tokens") or 1000, 800)
        if not profile.agent_prompt_id:
            payload["input"] = (
                profile.prompt.replace("{{course_goal}}", variables["course_goal"])
                .replace("{{module}}", variables["module"])
                .replace("{{rejected_urls}}", variables["rejected_urls"])
            )
            payload["input"] = "\n\n".join(
                [
                    payload["input"],
                    "Ограничение объёма: верни максимум 5 лучших кандидатов. "
                    "Для каждого кандидата нужны только title и url.",
                ]
            )
            if payload.get("tools"):
                for tool in payload["tools"]:
                    if tool.get("type") == "web_search":
                        tool["search_context_size"] = "low"
        else:
            payload["input"] = (
                "Найди до 5 лучших бесплатных русскоязычных материалов для модуля. "
                "Верни только JSON с candidates; у каждого кандидата только title и url."
            )
        return payload

    def search_module_materials(
        self,
        module: CourseModule,
        material_kind: str,
        rejected_urls: list[str] | None = None,
    ) -> list[dict]:
        profile = (
            WebSearchProfile.objects.filter(material_kind=material_kind, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if profile is None:
            raise WebSearchProfile.DoesNotExist(f"No active Web Search profile for {material_kind}")

        step = (
            PipelineRun.Step.VIDEO_SEARCH
            if material_kind == WebSearchProfile.MaterialKind.VIDEO
            else PipelineRun.Step.TEXT_SEARCH
        )
        run = PipelineRun.objects.create(
            learner=module.course.learner,
            course=module.course,
            step=step,
            status=PipelineRun.Status.RUNNING,
            input_payload={"module_id": module.id, "material_kind": material_kind, "rejected_urls": rejected_urls or []},
        )
        try:
            payload = self.build_material_search_request(module, material_kind, rejected_urls)
            data = self.llm_client.create_json(payload)
            candidates = self._valid_candidates(self._extract_list_response(data, "candidates"))
            self.save_search_candidates(module, profile, candidates, raw_payload=data)
            run.mark_finished(PipelineRun.Status.SUCCESS, {"created_candidates": len(candidates), "raw": data})
            return candidates
        except Exception as exc:
            run.mark_finished(PipelineRun.Status.FAILED, error_message=str(exc))
            raise

    @transaction.atomic
    def save_search_candidates(
        self,
        module: CourseModule,
        search_profile: WebSearchProfile,
        candidates: list[dict],
        raw_payload: dict | None = None,
    ) -> int:
        created = 0
        for candidate in candidates:
            _, was_created = MaterialCandidate.objects.get_or_create(
                module=module,
                url=candidate["url"],
                defaults={
                    "title": candidate["title"],
                    "material_kind": search_profile.material_kind,
                    "search_profile": search_profile,
                    "raw_payload": raw_payload or {},
                },
            )
            created += int(was_created)
        return created

    def build_structuring_request(self, module: CourseModule) -> dict:
        candidates = [
            {
                "title": self._truncate(candidate["title"], 180),
                "url": self._truncate(candidate["url"], 500),
                "material_kind": candidate["material_kind"],
            }
            for candidate in module.material_candidates.exclude(status=MaterialCandidate.Status.REJECTED).values(
                "title",
                "url",
                "material_kind",
            )
        ]

        candidates = self._prioritize_candidates(candidates)[:MAX_CANDIDATES_FOR_STRUCTURING]

        prompt = "\n\n".join(
            [
                self.llm_settings.material_structuring_prompt,
                f"Цель курса: {self._truncate(module.course.goal, MAX_GOAL_CHARS)}",
                f"Модуль: {self._module_context(module, compact=True)}",
                f"Кандидаты: {self._compact_json(candidates, 5000)}",
            ]
        )

        payload = self._base_llm_payload(
            prompt,
            model=self.llm_settings.resolve_chat_model_uri(),
        )

        payload["max_output_tokens"] = max(self.llm_settings.max_output_tokens, 3000)

        return payload

    def structure_module_materials(self, module: CourseModule) -> list[ModuleElement]:
        run = PipelineRun.objects.create(
            learner=module.course.learner,
            course=module.course,
            step=PipelineRun.Step.STRUCTURING,
            status=PipelineRun.Status.RUNNING,
            input_payload={"module_id": module.id},
        )
        try:
            payload = self.build_structuring_request(module)
            data = self.llm_client.create_json(payload, purpose="chat")
            data = self._normalize_list_container(data, "elements")
            elements = self.apply_structured_elements(module, data)
            run.mark_finished(PipelineRun.Status.SUCCESS, {"created_elements": len(elements), "raw": data})
            return elements
        except Exception as exc:
            run.mark_finished(PipelineRun.Status.FAILED, error_message=str(exc))
            raise

    @transaction.atomic
    def apply_structured_elements(self, module: CourseModule, data: dict) -> list[ModuleElement]:
        module.elements.all().delete()
        created_elements = []
        candidate_urls = set(module.material_candidates.values_list("url", flat=True))
        for index, element_data in enumerate(data.get("elements") or [], start=1):
            material_data = element_data.get("material") or {}
            url = material_data.get("url")
            if not url or url not in candidate_urls:
                continue
            material = self._upsert_material(material_data)
            element_type = self._element_type(element_data.get("element_type"))
            element = ModuleElement.objects.create(
                module=module,
                material=material,
                order=index,
                element_type=element_type,
                title=str(element_data.get("title") or material.title)[:240],
                short_description=str(element_data.get("short_description") or material.summary),
                acquired_competencies=self._list(element_data.get("acquired_competencies") or material.competencies),
                estimated_minutes=self._positive_int(
                    element_data.get("estimated_minutes") or material.estimated_minutes
                ),
                recommendation_reason=str(element_data.get("recommendation_reason") or ""),
                is_required=bool(element_data.get("is_required", True)),
            )
            MaterialCandidate.objects.filter(module=module, url=url).update(status=MaterialCandidate.Status.ACCEPTED)
            created_elements.append(element)
        return created_elements

    def build_replacement_request(self, feedback: MaterialFeedback) -> dict:
        module = feedback.element.module
        rejected_urls = []
        if feedback.element.material_id:
            rejected_urls.append(feedback.element.material.url)
        kind = feedback.replacement_kind
        if not kind and feedback.element.material:
            kind = (
                WebSearchProfile.MaterialKind.VIDEO
                if feedback.element.material.format == "video"
                else WebSearchProfile.MaterialKind.TEXT
            )
        return self.build_material_search_request(module, kind or WebSearchProfile.MaterialKind.TEXT, rejected_urls)

    def replace_element_material(self, feedback: MaterialFeedback) -> ModuleElement | None:
        module = feedback.element.module
        kind = feedback.replacement_kind
        if not kind and feedback.element.material:
            kind = (
                WebSearchProfile.MaterialKind.VIDEO
                if feedback.element.material.format == LearningMaterial.Format.VIDEO
                else WebSearchProfile.MaterialKind.TEXT
            )
        rejected_urls = list(
            module.material_candidates.filter(status=MaterialCandidate.Status.REJECTED).values_list("url", flat=True)
        )
        if feedback.element.material:
            rejected_urls.append(feedback.element.material.url)
            MaterialCandidate.objects.filter(module=module, url=feedback.element.material.url).update(
                status=MaterialCandidate.Status.REJECTED,
                rejection_reason=feedback.get_rating_display(),
            )

        self.search_module_materials(module, kind or WebSearchProfile.MaterialKind.TEXT, rejected_urls=rejected_urls)
        payload = self.build_structuring_request(module)
        run = PipelineRun.objects.create(
            learner=module.course.learner,
            course=module.course,
            step=PipelineRun.Step.ADAPTATION,
            status=PipelineRun.Status.RUNNING,
            input_payload={"feedback_id": feedback.id, "element_id": feedback.element_id},
        )
        try:
            data = self.llm_client.create_json(payload, purpose="chat")
            data = self._normalize_list_container(data, "elements")
            replacement = self._replace_single_element(feedback.element, data)
            run.mark_finished(
                PipelineRun.Status.SUCCESS,
                {"replacement_element_id": replacement.id if replacement else None, "raw": data},
            )
            return replacement
        except Exception as exc:
            run.mark_finished(PipelineRun.Status.FAILED, error_message=str(exc))
            raise

    def _base_llm_payload(self, input_prompt: str, model: str) -> dict:
        return {
            "model": model,
            "input": input_prompt,
            "temperature": float(self.llm_settings.temperature),
            "top_p": float(self.llm_settings.top_p),
            "max_output_tokens": self.llm_settings.max_output_tokens,
            **(self.llm_settings.extra_options or {}),
        }

    def _module_context(self, module: CourseModule, compact: bool = False) -> str:
        def field(value, limit=MAX_MODULE_FIELD_CHARS):
            return self._truncate(value, limit) if compact else value

        return "\n".join(
            [
                f"Название: {field(module.title, 240)}",
                f"Описание: {field(module.description)}",
                f"Результаты обучения: {self._compact_json(module.learning_outcomes, 900) if compact else module.learning_outcomes}",
                f"Компетенции: {self._compact_json(module.competencies, 900) if compact else module.competencies}",
                f"Где применяются навыки: {field(module.use_cases)}",
                f"Актуальность: {field(module.market_relevance)}",
                f"Трудоёмкость: {module.total_effort_hours} ч",
            ]
        )

    def _replace_single_element(self, element: ModuleElement, data: dict) -> ModuleElement | None:
        candidate_urls = set(element.module.material_candidates.values_list("url", flat=True))
        for element_data in data.get("elements") or []:
            material_data = element_data.get("material") or {}
            url = material_data.get("url")
            if not url or url not in candidate_urls:
                continue
            if element.material and url == element.material.url:
                continue
            material = self._upsert_material(material_data)
            element.material = material
            element.element_type = self._element_type(element_data.get("element_type"))
            element.title = str(element_data.get("title") or material.title)[:240]
            element.short_description = str(element_data.get("short_description") or material.summary)
            element.acquired_competencies = self._list(
                element_data.get("acquired_competencies") or material.competencies
            )
            element.estimated_minutes = self._positive_int(
                element_data.get("estimated_minutes") or material.estimated_minutes
            )
            element.recommendation_reason = str(element_data.get("recommendation_reason") or "")
            element.is_required = bool(element_data.get("is_required", True))
            element.save()
            MaterialCandidate.objects.filter(module=element.module, url=url).update(status=MaterialCandidate.Status.ACCEPTED)
            return element
        return None

    def _upsert_material(self, material_data: dict) -> LearningMaterial:
        url = material_data["url"]
        material_format = self._material_format(material_data.get("format"), url)
        defaults = {
            "title": str(material_data.get("title") or url)[:300],
            "format": material_format,
            "source": str(material_data.get("source") or self._source_from_url(url))[:160],
            "language": "ru",
            "access": LearningMaterial.Access.FREE,
            "summary": str(material_data.get("summary") or ""),
            "competencies": self._list(material_data.get("competencies")),
            "estimated_minutes": self._positive_int(material_data.get("estimated_minutes")),
            "quality_score": min(self._positive_int(material_data.get("quality_score")), 100),
            "metadata": {"llm_structured": True},
        }
        material, _ = LearningMaterial.objects.update_or_create(url=url, defaults=defaults)
        return material

    @staticmethod
    def _valid_candidates(candidates: list[dict]) -> list[dict]:
        valid = []
        seen = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            title = str(candidate.get("title") or "").strip()
            url = str(candidate.get("url") or "").strip()
            if not title or not url or url in seen:
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            seen.add(url)
            valid.append({"title": title[:300], "url": url})
        return valid

    @staticmethod
    def _list(value) -> list:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @classmethod
    def _extract_list_response(cls, data, key: str) -> list:
        return cls._normalize_list_container(data, key).get(key) or []

    @staticmethod
    def _normalize_object_response(data, response_name: str) -> dict:
        if isinstance(data, dict):
            return data
        raise LLMResponseError(
            f"LLM вернула JSON неверного формата для {response_name}: ожидался объект, получен {type(data).__name__}."
        )

    @classmethod
    def _normalize_list_container(cls, data, key: str) -> dict:
        if isinstance(data, dict):
            value = data.get(key)
            if value is None:
                return {**data, key: []}
            if isinstance(value, list):
                return data
            raise LLMResponseError(
                f"LLM вернула JSON неверного формата: поле {key} должно быть массивом."
            )
        if isinstance(data, list):
            return {key: data}
        return cls._normalize_object_response(data, key)

    @staticmethod
    def _decimal(value) -> Decimal:
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.1"))
        except (InvalidOperation, ValueError):
            return Decimal("0.0")

    @staticmethod
    def _positive_int(value) -> int:
        try:
            return max(int(float(value or 0)), 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _element_type(value: str) -> str:
        allowed = {choice for choice, _ in ModuleElement.ElementType.choices}
        return value if value in allowed else ModuleElement.ElementType.THEORY

    @staticmethod
    def _material_format(value: str, url: str) -> str:
        allowed = {choice for choice, _ in LearningMaterial.Format.choices}
        if value in allowed:
            return value
        host = urlparse(url).netloc.lower()
        if any(domain in host for domain in ("youtube.com", "youtu.be", "rutube.ru", "vk.com", "vkvideo.ru")):
            return LearningMaterial.Format.VIDEO
        if "github.com" in host or "gitverse.ru" in host:
            return LearningMaterial.Format.REPOSITORY
        return LearningMaterial.Format.ARTICLE

    @staticmethod
    def _source_from_url(url: str) -> str:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host or "web"

    @staticmethod
    def _truncate(value, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @classmethod
    def _compact_json(cls, value, limit: int) -> str:
        text = json.dumps({} if value is None else value, ensure_ascii=False, separators=(",", ":"), default=str)
        return cls._truncate(text, limit)

    @staticmethod
    def _prioritize_candidates(candidates: list[dict]) -> list[dict]:
        videos = [
            candidate
            for candidate in candidates
            if candidate.get("material_kind") == WebSearchProfile.MaterialKind.VIDEO
        ]
        texts = [
            candidate
            for candidate in candidates
            if candidate.get("material_kind") != WebSearchProfile.MaterialKind.VIDEO
        ]
        prioritized = []
        for pair in zip(videos, texts):
            prioritized.extend(pair)
        prioritized.extend(videos[len(texts) :])
        prioritized.extend(texts[len(videos) :])
        return prioritized
