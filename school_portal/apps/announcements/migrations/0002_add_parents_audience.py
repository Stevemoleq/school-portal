from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcement',
            name='target_audience',
            field=models.CharField(choices=[('all', 'Everyone'), ('students', 'Students Only'), ('teachers', 'Teachers Only'), ('parents', 'Parents Only')], default='all', max_length=10),
        ),
    ]
