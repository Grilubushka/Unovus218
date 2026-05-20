from django.db import migrations, models


def configure_default_chat(apps, schema_editor):
    LLMSettings = apps.get_model("learning", "LLMSettings")
    for settings in LLMSettings.objects.all():
        settings.chat_provider = "openai_compatible"
        settings.chat_api_base_url_env = "DEFAULT_LLM_BASE_URL"
        settings.chat_api_key_env = "DEFAULT_LLM_API_KEY"
        settings.default_chat_model = "gpt-4o-mini"
        settings.save(
            update_fields=[
                "chat_provider",
                "chat_api_base_url_env",
                "chat_api_key_env",
                "default_chat_model",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0003_relax_default_web_search_domains"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmsettings",
            name="chat_provider",
            field=models.CharField(
                choices=[
                    ("yandex", "Yandex Cloud"),
                    ("openai_compatible", "OpenAI-compatible"),
                    ("other", "Другое"),
                ],
                default="openai_compatible",
                max_length=32,
                verbose_name="DEFAULT_CHAT провайдер",
            ),
        ),
        migrations.AddField(
            model_name="llmsettings",
            name="chat_api_base_url",
            field=models.URLField(blank=True, verbose_name="DEFAULT_CHAT API base URL"),
        ),
        migrations.AddField(
            model_name="llmsettings",
            name="chat_api_base_url_env",
            field=models.CharField(
                default="DEFAULT_LLM_BASE_URL",
                max_length=120,
                verbose_name="env с DEFAULT_CHAT base URL",
            ),
        ),
        migrations.AddField(
            model_name="llmsettings",
            name="chat_api_key_env",
            field=models.CharField(
                default="DEFAULT_LLM_API_KEY",
                max_length=120,
                verbose_name="env с DEFAULT_CHAT API key",
            ),
        ),
        migrations.AlterField(
            model_name="llmsettings",
            name="default_chat_model",
            field=models.CharField(default="gpt-4o-mini", max_length=160, verbose_name="DEFAULT_CHAT_MODEL"),
        ),
        migrations.RunPython(configure_default_chat, migrations.RunPython.noop),
    ]
