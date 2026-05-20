from unittest.mock import patch

from django.test import TestCase

from learning.models import Course, CourseModule, LLMSettings, WebSearchProfile
from learning.services.llm import LLMResponseError, ResponsesLLMClient
from learning.services.pipeline import CoursePipeline


class RecordingLLMClient:
    def __init__(self):
        self.calls = []

    def create_json(self, payload, purpose="default"):
        self.calls.append((payload, purpose))
        return {"elements": []}


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
        self.assertEqual(video_payload["max_output_tokens"], 1000)
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
