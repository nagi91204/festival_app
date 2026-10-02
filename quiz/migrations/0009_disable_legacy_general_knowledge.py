from django.db import migrations


def disable_legacy_questions(apps, schema_editor):
    Question = apps.get_model("quiz", "Question")
    Question.objects.filter(title__startswith="一般常識 ").update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [("quiz", "0008_refresh_for_elementary_quiz")]

    operations = [migrations.RunPython(disable_legacy_questions, migrations.RunPython.noop)]
