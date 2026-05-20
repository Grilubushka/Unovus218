import json
import unittest

from bot.application.onboarding_payload import (
    SCHEMA_VERSION,
    build_admin_onboarding_json,
    build_admin_onboarding_payload,
)


class AdminOnboardingPayloadTest(unittest.TestCase):
    def test_builds_backend_ready_payload(self) -> None:
        profile = {
            "goal": "wants to learn a skill",
            "goal_code": "skill",
            "goal_tone": "focused",
            "interest": "wants to learn Python",
            "interest_code": "python",
            "interest_tone": "tech",
            "constraints": "needs structure; needs practice",
            "constraints_code": "chaos,no_practice",
            "constraints_tone": "anti-chaos, practice",
        }
        answers = [
            {
                "step": 1,
                "question_code": "goal",
                "question_title": "Goal",
                "profile_key": "goal",
                "answer_code": "skill",
                "answer_label": "Learn skill",
                "answer_value": "wants to learn a skill",
                "source": "button",
                "created_at": "2026-05-21 10:00:00",
            },
            {
                "step": 7,
                "question_code": "constraints",
                "question_title": "Constraints",
                "profile_key": "constraints",
                "answer_code": "chaos,no_practice",
                "answer_label": "Structure, Practice",
                "answer_value": "needs structure; needs practice",
                "source": "multi_button",
                "created_at": "2026-05-21 10:03:00",
            },
        ]

        payload = build_admin_onboarding_payload(
            telegram_user_id=123,
            chat_id=456,
            quiz_session_id=7,
            course_session_id=8,
            profile=profile,
            answers=answers,
            route=[{"title": "Start"}],
            user={"username": "tester", "first_name": "Test"},
            submitted_at="2026-05-21T10:04:00+00:00",
        )

        self.assertEqual(payload["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(payload["telegramUserId"], 123)
        self.assertEqual(payload["profile"]["constraints"]["codes"], ["chaos", "no_practice"])
        self.assertEqual(payload["answers"][1]["answer"]["codes"], ["chaos", "no_practice"])
        self.assertEqual(payload["route"], [{"title": "Start"}])
        self.assertEqual(payload["user"]["username"], "tester")

        encoded = build_admin_onboarding_json(payload)
        self.assertEqual(json.loads(encoded)["schemaVersion"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
