import unittest

from bot.application.onboarding_adaptation import clean_generated_text


class OnboardingAdaptationTest(unittest.TestCase):
    def test_rejects_people_based_learning_promises(self) -> None:
        self.assertEqual(clean_generated_text("Наставник проверит работу", 80), "")
        self.assertEqual(clean_generated_text("Будет обратная связь от специалиста", 80), "")
        self.assertEqual(clean_generated_text("Запланируй созвон с экспертом", 80), "")

    def test_rejects_disallowed_english_product_words(self) -> None:
        self.assertEqual(clean_generated_text("Открой Mini App и собери roadmap", 80), "")
        self.assertEqual(clean_generated_text("Добавим feedback после каждого sprint", 80), "")


if __name__ == "__main__":
    unittest.main()
