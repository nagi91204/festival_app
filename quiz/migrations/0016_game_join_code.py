import secrets

from django.db import migrations, models


def backfill_join_codes(apps, schema_editor):
    Game = apps.get_model("quiz", "Game")
    used = set(Game.objects.exclude(join_code=None).values_list("join_code", flat=True))
    for game in Game.objects.filter(join_code__isnull=True):
        for _ in range(200):
            code = f"{secrets.randbelow(10000):04d}"
            if code not in used:
                break
        else:
            code = f"{secrets.randbelow(1000000):06d}"
            while code in used:
                code = f"{secrets.randbelow(1000000):06d}"
        used.add(code)
        game.join_code = code
        game.save(update_fields=["join_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0015_merge_teacher_quizzes_and_video_question"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="join_code",
            field=models.CharField(max_length=6, null=True, blank=True, editable=False),
        ),
        migrations.RunPython(backfill_join_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="game",
            name="join_code",
            field=models.CharField(max_length=6, unique=True, editable=False),
        ),
    ]
