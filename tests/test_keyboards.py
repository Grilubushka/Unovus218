import unittest

from bot.presentation.keyboards import miniapp_url_for_user


class MiniAppKeyboardTest(unittest.TestCase):
    def test_adds_telegram_user_id_to_webapp_url(self) -> None:
        url = miniapp_url_for_user("https://example.org/app?theme=dark#top", 42)

        self.assertEqual(url, "https://example.org/app?theme=dark&telegram_user_id=42#top")

    def test_replaces_existing_user_id_parameters(self) -> None:
        url = miniapp_url_for_user("https://example.org/?user_id=1&telegram_user_id=2", 42)

        self.assertEqual(url, "https://example.org/?telegram_user_id=42")


if __name__ == "__main__":
    unittest.main()
