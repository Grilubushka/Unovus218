from base64 import b64encode
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings

from learning.models import (
    Certificate,
    Course,
    CourseModule,
    LearnerProfile,
    LearningMaterial,
    LLMSettings,
    MaterialCandidate,
    MaterialFeedback,
    ModuleElement,
    WebSearchProfile,
)
from learning.services.llm import LLMResponseError, ResponsesLLMClient
from learning.services.pipeline import CoursePipeline


class RecordingLLMClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"elements": []}

    def create_json(self, payload, purpose="default"):
        self.calls.append((payload, purpose))
        return self.response


class PipelineRoutingTests(TestCase):
    def setUp(self):
        self.llm_settings = LLMSettings.get_solo()
        self.llm_settings.provider = LLMSettings.Provider.YANDEX
        self.llm_settings.default_model = "yandexgpt/latest"
        self.llm_settings.chat_provider = LLMSettings.Provider.OPENAI_COMPATIBLE
        self.llm_settings.default_chat_model = "gpt-4o-mini"
        self.llm_settings.save()

        self.course = Course.objects.create(title="Python", goal="Изучить Python")
        self.module = CourseModule.objects.create(
            course=self.course,
            order=1,
            title="Основы Python",
            description="Синтаксис, типы данных и простые программы",
        )

    @patch.dict("os.environ", {"YANDEX_CLOUD_FOLDER": "folder-id", "DEFAULT_CHAT_MODEL": "gpt-4o-mini"})
    def test_web_search_profiles_use_yandex_prompt_agents_for_video_and_text(self):
        pipeline = CoursePipeline(llm_settings=self.llm_settings)

        video_payload = pipeline.build_material_search_request(
            self.module,
            WebSearchProfile.MaterialKind.VIDEO,
        )
        text_payload = pipeline.build_material_search_request(
            self.module,
            WebSearchProfile.MaterialKind.TEXT,
        )

        self.assertEqual(video_payload["prompt"]["id"], "fvtldhocqqkp1134gh6h")
        self.assertEqual(text_payload["prompt"]["id"], "fvt6v70mkbvmii8v56u6")
        self.assertEqual(video_payload["prompt"]["variables"]["course_goal"], "Изучить Python")
        self.assertIn("Основы Python", video_payload["prompt"]["variables"]["module"])
        self.assertEqual(video_payload["prompt"]["variables"]["rejected_urls"], "[]")
        self.assertEqual(video_payload["max_output_tokens"], 800)
        self.assertIn("до 5", video_payload["input"])
        self.assertNotIn("model", video_payload)
        self.assertNotIn("tools", video_payload)

    @patch.dict("os.environ", {"DEFAULT_CHAT_MODEL": "gpt-4o-mini"})
    def test_structuring_uses_default_chat_model(self):
        llm_client = RecordingLLMClient()
        pipeline = CoursePipeline(llm_settings=self.llm_settings, llm_client=llm_client)

        pipeline.structure_module_materials(self.module)

        payload, purpose = llm_client.calls[0]
        self.assertEqual(purpose, "chat")
        self.assertEqual(payload["model"], "gpt-4o-mini")

    @patch.dict("os.environ", {"DEFAULT_CHAT_MODEL": "gpt-4o-mini"})
    def test_structuring_payload_stays_compact(self):
        video_profile = WebSearchProfile.objects.get(material_kind=WebSearchProfile.MaterialKind.VIDEO)
        text_profile = WebSearchProfile.objects.get(material_kind=WebSearchProfile.MaterialKind.TEXT)
        long_title = "Очень длинное название " * 40
        long_url = "https://example.com/" + ("very-long-path/" * 80)

        for index in range(10):
            profile = video_profile if index % 2 == 0 else text_profile
            MaterialCandidate.objects.create(
                module=self.module,
                search_profile=profile,
                material_kind=profile.material_kind,
                title=f"{index} {long_title}",
                url=f"{long_url}{index}",
            )

        payload = CoursePipeline(llm_settings=self.llm_settings).build_structuring_request(self.module)

        self.assertLess(len(payload["input"]), 9000)
        self.assertEqual(payload["input"].count('"url"'), 6)
        self.assertIn('"material_kind":"video"', payload["input"])
        self.assertIn('"material_kind":"text"', payload["input"])

    @patch.dict("os.environ", {"DEFAULT_CHAT_MODEL": "gpt-4o-mini"})
    def test_search_accepts_bare_candidate_list(self):
        llm_client = RecordingLLMClient(
            response=[{"title": "Python lesson", "url": "https://example.com/python"}]
        )
        pipeline = CoursePipeline(llm_settings=self.llm_settings, llm_client=llm_client)

        candidates = pipeline.search_module_materials(self.module, WebSearchProfile.MaterialKind.TEXT)

        self.assertEqual(candidates, [{"title": "Python lesson", "url": "https://example.com/python"}])

    @patch.dict("os.environ", {"DEFAULT_CHAT_MODEL": "gpt-4o-mini"})
    def test_structuring_accepts_bare_element_list(self):
        profile = WebSearchProfile.objects.get(material_kind=WebSearchProfile.MaterialKind.TEXT)
        MaterialCandidate.objects.create(
            module=self.module,
            search_profile=profile,
            material_kind=profile.material_kind,
            title="Python article",
            url="https://example.com/python-article",
        )
        llm_client = RecordingLLMClient(
            response=[
                {
                    "title": "Read Python article",
                    "element_type": "theory",
                    "material": {
                        "title": "Python article",
                        "url": "https://example.com/python-article",
                        "format": "article",
                    },
                }
            ]
        )
        pipeline = CoursePipeline(llm_settings=self.llm_settings, llm_client=llm_client)

        elements = pipeline.structure_module_materials(self.module)

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].material.url, "https://example.com/python-article")


class LLMResponseTests(TestCase):
    def test_failed_response_raises_provider_error(self):
        response = {
            "status": "failed",
            "error": {
                "code": "model_call_error",
                "message": "Error while calling model: 400: text generation size exceeded",
            },
            "output": [{"type": "web_search_call", "status": "completed"}],
        }

        with self.assertRaisesMessage(
            LLMResponseError,
            "LLM вернула ошибку (failed): model_call_error: Error while calling model",
        ):
            ResponsesLLMClient.raise_for_failed_response(response)


@override_settings(ADMIN_API_TOKEN="secret", DEBUG=True)
class MiniAppApiTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_onboarding_endpoint_rejects_invalid_token(self):
        response = self.client.post(
            "/api/onboarding/complete",
            data={"telegramUserId": 123},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong",
        )

        self.assertEqual(response.status_code, 401)

    def test_onboarding_endpoint_creates_learner_and_course(self):
        def build_course(learner, user_goal):
            return Course.objects.create(
                learner=learner,
                title="Django route",
                goal=user_goal.goal,
                initial_level=user_goal.current_level,
                target_level=user_goal.target_level,
                status=Course.Status.READY,
            )

        payload = {
            "schemaVersion": "admin.onboarding.v1",
            "telegramUserId": 123,
            "profile": {
                "goal": {"value": "Научиться Django"},
                "interest": {"value": "Backend"},
                "level": {"value": "Начинающий"},
                "focus": {"value": "Собрать API"},
            },
            "answers": [{"questionTitle": "Цель", "answer": {"value": "Django"}}],
            "user": {"firstName": "Ada", "lastName": "Lovelace"},
        }

        with patch("learning.services.miniapp_api.CoursePipeline") as pipeline_class:
            pipeline_class.return_value.build_course_from_goal.side_effect = build_course
            response = self.client.post(
                "/api/onboarding/complete",
                data=payload,
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer secret",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(LearnerProfile.objects.filter(telegram_id="123", display_name="Ada Lovelace").exists())
        course = Course.objects.get()
        self.assertEqual(course.goal, "Научиться Django")
        self.assertIn("adminOnboardingPayload", course.profile_snapshot)

    def test_roadmap_endpoint_returns_required_and_building_states(self):
        missing_response = self.client.get("/api/roadmap")
        self.assertEqual(missing_response.json()["reason"], "telegram_user_id_required")

        learner = LearnerProfile.objects.create(telegram_id="321", display_name="Builder")
        Course.objects.create(learner=learner, title="Building", goal="Build", status=Course.Status.BUILDING)

        response = self.client.get("/api/roadmap?telegram_user_id=321")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["hasData"])
        self.assertEqual(response.json()["reason"], "course_building")

    def test_roadmap_endpoint_returns_ready_course(self):
        course, module, element = self.create_ready_course()

        response = self.client.get("/api/roadmap?telegram_user_id=555")

        payload = response.json()
        self.assertTrue(payload["hasData"])
        self.assertEqual(payload["courseId"], course.id)
        self.assertEqual(payload["modules"][0]["title"], module.title)
        self.assertEqual(payload["modules"][0]["sections"][0]["topics"][0]["materials"][0]["elementId"], element.id)
        self.assertEqual(payload["modules"][0]["sections"][0]["topics"][0]["materials"][0]["url"], element.material.url)

    def test_progress_endpoint_marks_module_and_course(self):
        course, module, _ = self.create_ready_course()

        response = self.client.post(
            "/api/progress/mark",
            data={"courseId": course.id, "moduleIndex": 0, "telegramUserId": 555},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        module.refresh_from_db()
        course.refresh_from_db()
        self.assertEqual(module.status, CourseModule.Status.COMPLETED)
        self.assertEqual(course.status, Course.Status.COMPLETED)

    def test_feedback_endpoint_creates_feedback_and_runs_replacement(self):
        course, _, element = self.create_ready_course()

        with patch("learning.services.miniapp_api.CoursePipeline") as pipeline_class:
            pipeline_class.return_value.replace_element_material.return_value = element
            response = self.client.post(
                "/api/feedback",
                data={"courseId": course.id, "moduleIndex": 0, "telegramUserId": 555, "feedback": "replace"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        feedback = MaterialFeedback.objects.get()
        self.assertEqual(feedback.rating, MaterialFeedback.Rating.UNSUITABLE)
        pipeline_class.return_value.replace_element_material.assert_called_once_with(feedback)

    def test_certificate_upload_saves_file_and_certificate(self):
        LearnerProfile.objects.create(telegram_id="777", display_name="Cert User")
        data_url = "data:text/plain;base64," + b64encode(b"certificate").decode("ascii")

        response = self.client.post(
            "/api/certificates/upload",
            data={
                "telegramUserId": 777,
                "title": "Python Certificate",
                "fileName": "python.txt",
                "fileType": "text/plain",
                "dataUrl": data_url,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        certificate = Certificate.objects.get()
        self.assertEqual(certificate.title, "Python Certificate")
        self.assertTrue(certificate.file.name.endswith(".txt"))

    def create_ready_course(self):
        learner = LearnerProfile.objects.create(telegram_id="555", display_name="Mini User")
        course = Course.objects.create(
            learner=learner,
            title="Django API",
            goal="Изучить Django API",
            status=Course.Status.READY,
            recommendation_summary="Персональный курс",
        )
        module = CourseModule.objects.create(
            course=course,
            order=1,
            title="Основы API",
            description="HTTP и сериализация",
            learning_outcomes=["Понимать API"],
            competencies=["Django"],
        )
        material = LearningMaterial.objects.create(
            title="DRF guide",
            url="https://example.com/drf",
            format=LearningMaterial.Format.ARTICLE,
            source="example.com",
            estimated_minutes=15,
        )
        element = ModuleElement.objects.create(
            module=module,
            material=material,
            order=1,
            element_type=ModuleElement.ElementType.THEORY,
            title="Прочитать DRF guide",
            estimated_minutes=15,
        )
        return course, module, element
