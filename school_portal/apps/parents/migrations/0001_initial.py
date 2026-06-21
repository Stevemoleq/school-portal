from django.db import migrations, models
import django.db.models.deletion
import apps.parents.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('accounts', '0005_add_student_id_fields'),
        ('announcements', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Parent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parent_id', models.CharField(db_index=True, editable=False, max_length=20, unique=True)),
                ('phone_number', models.CharField(help_text='Primary phone number for login (e.g., 0991234567)', max_length=20, unique=True, validators=[apps.parents.models.validate_phone_number])),
                ('relationship', models.CharField(choices=[('father', 'Father'), ('mother', 'Mother'), ('guardian', 'Guardian'), ('grandparent', 'Grandparent'), ('aunt', 'Aunt'), ('uncle', 'Uncle'), ('other', 'Other')], default='guardian', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='parent', to='auth.user')),
            ],
            options={
                'verbose_name': 'Parent/Guardian',
                'verbose_name_plural': 'Parents/Guardians',
                'ordering': ['parent_id'],
            },
        ),
        migrations.CreateModel(
            name='ParentStudentRelationship',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary_contact', models.BooleanField(default=False, help_text='Primary contact for school communications')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_relationships', to='parents.parent')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_relationships', to='accounts.student')),
            ],
            options={
                'verbose_name': 'Parent-Student Relationship',
                'verbose_name_plural': 'Parent-Student Relationships',
                'ordering': ['parent', 'student'],
                'unique_together': {('parent', 'student')},
            },
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('status', models.CharField(choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late'), ('excused', 'Excused')], db_index=True, max_length=10)),
                ('term', models.CharField(choices=[('1st', 'First Term'), ('2nd', 'Second Term'), ('3rd', 'Third Term')], db_index=True, max_length=3)),
                ('session', models.CharField(db_index=True, max_length=9)),
                ('remarks', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_attendance', to='auth.user')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='accounts.student')),
            ],
            options={
                'verbose_name': 'Attendance Record',
                'verbose_name_plural': 'Attendance Records',
                'ordering': ['-date'],
                'unique_together': {('student', 'date', 'term', 'session')},
            },
        ),
        migrations.CreateModel(
            name='ParentNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('sms', 'SMS'), ('email', 'Email'), ('in_app', 'In-App'), ('push', 'Push Notification')], default='in_app', max_length=10)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('read', 'Read')], db_index=True, default='pending', max_length=10)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='parents.parent')),
                ('related_student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.student')),
            ],
            options={
                'verbose_name': 'Parent Notification',
                'verbose_name_plural': 'Parent Notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ParentAnnouncementRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('announcement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_by_parents', to='announcements.announcement')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_announcements', to='parents.parent')),
            ],
            options={
                'verbose_name': 'Parent Announcement Read Status',
                'verbose_name_plural': 'Parent Announcement Read Statuses',
                'unique_together': {('parent', 'announcement')},
            },
        ),
    ]
