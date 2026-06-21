"""
Schema + Data migration: Add student_id fields and populate existing students.
"""

import re
import threading
from django.db import migrations, models, connection

# Thread lock for safe sequence generation
_lock = threading.Lock()
SCHOOL_CODE = "NZS"


def get_form_display(form_name):
    form_name = (form_name or '').strip().lower()
    match = re.match(r'form\s*(\d+)', form_name)
    if match:
        return f"F{match.group(1)}"
    match = re.match(r'grade\s*(\d+)', form_name)
    if match:
        return f"G{match.group(1)}"
    match = re.match(r'senior\s*(\d+)', form_name)
    if match:
        return f"S{match.group(1)}"
    match = re.match(r'[fs](\d+)', form_name)
    if match:
        return f"{form_name[0].upper()}{match.group(1)}"
    return form_name[:2].upper() if form_name else 'NA'


def _get_next_sequence(cursor, prefix):
    with _lock:
        cursor.execute(
            "SELECT student_id FROM accounts_student WHERE student_id LIKE %s ORDER BY student_id DESC LIMIT 1",
            [f"{prefix}%"]
        )
        row = cursor.fetchone()
        if row and row[0]:
            try:
                return int(row[0].split("-")[-1]) + 1
            except ValueError:
                pass
        return 1


def populate_student_ids(apps, schema_editor):
    """Generate student_ids for all existing students."""
    Student = apps.get_model('accounts', 'Student')
    db_alias = schema_editor.connection.alias

    students = Student.objects.using(db_alias).all()
    print(f"\n  Populating Student IDs for {students.count()} students...")

    with connection.cursor() as cursor:
        for student in students.iterator():
            # Set admission year from created_at
            if not student.admission_year and student.created_at:
                student.admission_year = student.created_at.year

            # Set admission form from student_class name if available
            if not student.admission_form:
                if hasattr(student, 'student_class') and student.student_class:
                    student.admission_form = student.student_class.name
                else:
                    student.admission_form = 'Form 1'

            # Copy student_class to current_class if not set
            if not student.current_class_id:
                if hasattr(student, 'student_class_id') and student.student_class_id:
                    student.current_class_id = student.student_class_id

            year_2digit = str(student.admission_year)[-2:] if student.admission_year else '00'
            form_code = get_form_display(student.admission_form)
            prefix = f"{SCHOOL_CODE}-{year_2digit}-{form_code}-"
            seq = _get_next_sequence(cursor, prefix)
            student.student_id = f"{prefix}{seq:04d}"

            if not student.registration_number:
                student.registration_number = student.student_id

            student.save(update_fields=[
                'admission_year', 'admission_form', 'current_class',
                'student_id', 'registration_number',
            ])
            print(f"    -> {student.student_id}")

    print("  Done!")


def reverse_populate(apps, schema_editor):
    Student = apps.get_model('accounts', 'Student')
    Student.objects.all().update(
        student_id='',
        admission_year=None,
        admission_form='',
        current_class=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_rename_class_id_and_add_timestamps'),
    ]

    operations = [
        # Step 1: Add new fields WITHOUT unique constraint first
        migrations.AddField(
            model_name='student',
            name='student_id',
            field=models.CharField(
                db_index=True,
                default='',
                editable=False,
                help_text='Auto-generated Student ID',
                max_length=25,
            ),
        ),
        migrations.AddField(
            model_name='student',
            name='admission_year',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='student',
            name='admission_form',
            field=models.CharField(blank=True, default='Form 1', max_length=50),
        ),
        migrations.AddField(
            model_name='student',
            name='current_class',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=models.SET_NULL,
                related_name='students',
                to='accounts.class',
            ),
        ),

        # Step 2: Populate student_ids for existing students
        migrations.RunPython(populate_student_ids, reverse_populate),

        # Step 3: Add unique constraint on student_id
        migrations.RunSQL(
            sql=[
                "CREATE UNIQUE INDEX IF NOT EXISTS accounts_student_student_id_uniq ON accounts_student(student_id);",
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS accounts_student_student_id_uniq;",
            ],
        ),
    ]
