from django.db import migrations


def relax_default_domains(apps, schema_editor):
    WebSearchProfile = apps.get_model("learning", "WebSearchProfile")
    WebSearchProfile.objects.filter(
        name__in=[
            "WEB_SEARCH: бесплатные русскоязычные видео",
            "WEB_SEARCH: бесплатные русскоязычные тексты",
        ]
    ).update(allowed_domains=[])


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0002_seed_default_settings"),
    ]

    operations = [
        migrations.RunPython(relax_default_domains, migrations.RunPython.noop),
    ]
