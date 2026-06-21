import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_rename_class_id_and_add_timestamps'),
        ('results', '0004_alter_result_subject'),
    ]

    operations = [
        # Add related_name to Result.subject
        migrations.AlterField(
            model_name='result',
            name='subject',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='results',
                to='accounts.subject',
            ),
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='result',
            index=models.Index(
                fields=['student', 'term', 'session'],
                name='results_student_term_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(
                fields=['subject', 'term', 'session'],
                name='results_subject_term_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(
                fields=['-date_uploaded'],
                name='results_date_uploaded_idx',
            ),
        ),
    ]
