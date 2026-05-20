from django.db import migrations, models

import learning.models


def configure_prompt_agents(apps, schema_editor):
    WebSearchProfile = apps.get_model("learning", "WebSearchProfile")
    WebSearchProfile.objects.filter(material_kind="video").update(
        agent_prompt_id="fvtldhocqqkp1134gh6h",
        agent_input=learning.models.default_agent_input(),
    )
    WebSearchProfile.objects.filter(material_kind="text").update(
        agent_prompt_id="fvt6v70mkbvmii8v56u6",
        agent_input=learning.models.default_agent_input(),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0004_split_default_chat_provider"),
    ]

    operations = [
        migrations.AddField(
            model_name="websearchprofile",
            name="agent_prompt_id",
            field=models.CharField(blank=True, max_length=120, verbose_name="Yandex prompt id"),
        ),
        migrations.AddField(
            model_name="websearchprofile",
            name="agent_input",
            field=models.CharField(
                blank=True,
                default=learning.models.default_agent_input,
                max_length=300,
                verbose_name="input для prompt-агента",
            ),
        ),
        migrations.RunPython(configure_prompt_agents, migrations.RunPython.noop),
    ]
