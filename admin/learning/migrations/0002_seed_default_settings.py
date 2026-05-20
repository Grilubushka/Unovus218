from django.db import migrations

from learning.prompts import TEXT_SEARCH_PROMPT, VIDEO_SEARCH_PROMPT


def seed_defaults(apps, schema_editor):
    LLMSettings = apps.get_model("learning", "LLMSettings")
    WebSearchProfile = apps.get_model("learning", "WebSearchProfile")

    LLMSettings.objects.get_or_create(singleton_key="default", defaults={"title": "DEFAULT_LLM"})

    WebSearchProfile.objects.get_or_create(
        material_kind="video",
        name="WEB_SEARCH: бесплатные русскоязычные видео",
        defaults={
            "is_active": True,
            "prompt": VIDEO_SEARCH_PROMPT,
            "allowed_domains": ["youtube.com", "rutube.ru", "vk.com", "vkvideo.ru"],
            "search_context_size": "medium",
            "temperature": "0.30",
            "max_output_tokens": 1000,
        },
    )
    WebSearchProfile.objects.get_or_create(
        material_kind="text",
        name="WEB_SEARCH: бесплатные русскоязычные тексты",
        defaults={
            "is_active": True,
            "prompt": TEXT_SEARCH_PROMPT,
            "allowed_domains": [
                "stepik.org",
                "habr.com",
                "habr.ru",
                "practicum.yandex.ru",
                "htmlacademy.ru",
                "github.com",
            ],
            "search_context_size": "medium",
            "temperature": "0.30",
            "max_output_tokens": 1000,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
