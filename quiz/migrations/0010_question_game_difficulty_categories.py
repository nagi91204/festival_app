from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("quiz", "0009_disable_legacy_general_knowledge")]

    operations = [
        migrations.AddField(
            model_name="question",
            name="difficulty",
            field=models.CharField(
                choices=[("easy", "簡単"), ("normal", "普通"), ("hard", "ハード")],
                default="normal",
                max_length=10,
                verbose_name="難易度",
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="difficulty",
            field=models.CharField(
                choices=[("easy", "簡単"), ("normal", "普通"), ("hard", "ハード")],
                default="normal",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="selected_categories",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
