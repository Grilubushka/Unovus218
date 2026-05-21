import tempfile
import unittest
from pathlib import Path

from bot.infrastructure.miniapp_data import MiniAppDataRepository
from bot.infrastructure.onboarding_db import OnboardingDatabase


class MiniAppDataRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "bot.sqlite3")
        self.database = OnboardingDatabase(self.database_path)
        self.database.connect()
        self.database.init_schema()
        self.repository = MiniAppDataRepository(self.database_path)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_requires_telegram_user_id_instead_of_returning_latest_route(self) -> None:
        self._create_finished_route(telegram_user_id=101)

        payload = self.repository.get_roadmap()

        self.assertFalse(payload["hasData"])
        self.assertFalse(payload["hasCompletedOnboarding"])
        self.assertEqual(payload["reason"], "telegram_user_id_required")

    def test_returns_onboarding_required_when_user_has_no_finished_session(self) -> None:
        self.database.upsert_user({"id": 202, "first_name": "No Route"}, 202)
        self.database.create_session(202, total_steps=7, profile={})

        payload = self.repository.get_roadmap(202)

        self.assertFalse(payload["hasData"])
        self.assertFalse(payload["hasCompletedOnboarding"])
        self.assertEqual(payload["reason"], "onboarding_required")

    def test_does_not_fall_back_to_another_users_route(self) -> None:
        self._create_finished_route(telegram_user_id=303)
        self.database.upsert_user({"id": 404, "first_name": "New User"}, 404)

        payload = self.repository.get_roadmap(404)

        self.assertFalse(payload["hasData"])
        self.assertEqual(payload["reason"], "onboarding_required")

    def test_returns_current_users_completed_route(self) -> None:
        self._create_finished_route(telegram_user_id=505)

        payload = self.repository.get_roadmap(505)

        self.assertTrue(payload["hasData"])
        self.assertTrue(payload["hasCompletedOnboarding"])
        self.assertEqual(payload["telegramUserId"], 505)
        self.assertEqual(payload["modules"][0]["title"], "Стартовый модуль")

    def _create_finished_route(self, telegram_user_id: int) -> None:
        profile = {
            "goal": "хочет собрать маршрут",
            "interest": "хочет Python",
            "time": "30 минут в день",
        }
        self.database.upsert_user({"id": telegram_user_id, "first_name": "Done"}, telegram_user_id)
        session_id = self.database.create_session(telegram_user_id, total_steps=7, profile={})
        self.database.finish_session(session_id, profile, {"hero": "Маршрут готов"})
        self.database.create_course_session(
            user_id=telegram_user_id,
            quiz_session_id=session_id,
            profile=profile,
            route=[
                {
                    "title": "Стартовый модуль",
                    "description": "Проверить базу и выбрать первый шаг.",
                    "duration": "20 мин",
                    "materials": [],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
