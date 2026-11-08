from django.db import migrations


def group_teacher_quizzes(apps, schema_editor):
    Question = apps.get_model("quiz", "Question")
    Question.objects.filter(
        category__in=["古川さんクイズ", "中川さんクイズ", "大石さんクイズ"],
    ).update(category="先生クイズ")


class Migration(migrations.Migration):

    dependencies = [("quiz", "0011_add_teacher_quizzes")]

    operations = [migrations.RunPython(group_teacher_quizzes, migrations.RunPython.noop)]
