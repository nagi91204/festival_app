from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("quiz", "0013_prefix_teacher_question_bodies")]

    operations = [
        migrations.RemoveConstraint(
            model_name="gamequestion",
            name="no_duplicate_question_in_game",
        ),
    ]
