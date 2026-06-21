import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_teacher_user'),
    ]

    operations = [
        # Add related_name to Student.user
        migrations.AlterField(
            model_name='student',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student',
                to='auth.user',
            ),
        ),
        # Rename Subject.class_id to assigned_class
        migrations.RenameField(
            model_name='subject',
            old_name='class_id',
            new_name='assigned_class',
        ),
        # Add timestamps to Class
        migrations.AddField(
            model_name='class',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='class',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Add timestamps to Subject
        migrations.AddField(
            model_name='subject',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subject',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Add timestamps to Student
        migrations.AddField(
            model_name='student',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='student',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Add timestamps to Teacher
        migrations.AddField(
            model_name='teacher',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='teacher',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
