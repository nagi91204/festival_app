from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0016_game_join_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="max_questions",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="0は無制限。この問題数を出題し終えたらゲームを終了する。",
                verbose_name="出題数の上限",
            ),
        ),
    ]
