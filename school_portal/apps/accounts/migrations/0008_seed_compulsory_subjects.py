"""
Data migration: backfill Subject category/is_compulsory and assign compulsory
subjects to every existing student.

This migration is SAFE — it does not delete or modify any existing records.
- Existing Subject records are updated in place.
- Compulsory subjects that do not exist yet are created for every Class.
- Every existing Student is enrolled in every compulsory Subject.
- Existing Result records are NOT touched.
"""
from django.db import migrations


COMPULSORY = {
    'English': 'ENG',
    'Mathematics': 'MATH',
    'Chichewa': 'CHIC',
    'Biology': 'BIO',
}

# Map subject names to category. Anything not listed falls back to OTHER.
CATEGORY_BY_NAME = {
    # Science
    'Physics': 'SCIENCE',
    'Chemistry': 'SCIENCE',
    'Biology': 'SCIENCE',
    'Agriculture': 'SCIENCE',
    'Computer Studies': 'SCIENCE',
    'Science': 'SCIENCE',
    # Humanities
    'History': 'HUMANITIES',
    'Geography': 'HUMANITIES',
    'Bible Knowledge': 'HUMANITIES',
    'Bible': 'HUMANITIES',
    'Religious Education': 'HUMANITIES',
    'Social Studies': 'HUMANITIES',
    'Chichewa': 'HUMANITIES',
    'English': 'HUMANITIES',
    # Commercial
    'Commerce': 'COMMERCIAL',
    'Accounting': 'COMMERCIAL',
    'Business Studies': 'COMMERCIAL',
    'Economics': 'COMMERCIAL',
    # Technical
    'Technical Drawing': 'TECHNICAL',
    'Woodwork': 'TECHNICAL',
    'Metalwork': 'TECHNICAL',
    'Home Economics': 'TECHNICAL',
    # Core
    'Mathematics': 'CORE',
}


def category_for(name):
    return CATEGORY_BY_NAME.get(name, 'OTHER')


def forward(apps, schema_editor):
    Subject = apps.get_model('accounts', 'Subject')
    Student = apps.get_model('accounts', 'Student')
    StudentSubject = apps.get_model('accounts', 'StudentSubject')
    Class = apps.get_model('accounts', 'Class')

    # 0. Repair the auto-increment sequence in case it is out of sync
    # with the actual primary key values. This is a common issue when
    # rows were inserted with explicit IDs (e.g. data seeding or restore).
    from django.db import connection
    
    # Only run PostgreSQL-specific sequence repair on PostgreSQL
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('accounts_subject', 'id'),
                    COALESCE((SELECT MAX(id) FROM accounts_subject), 0) + 1,
                    false
                )
            """)
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('accounts_class', 'id'),
                    COALESCE((SELECT MAX(id) FROM accounts_class), 0) + 1,
                    false
                )
            """)
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('accounts_student', 'id'),
                    COALESCE((SELECT MAX(id) FROM accounts_student), 0) + 1,
                    false
                )
            """)
            cursor.execute("""
                SELECT setval(
                    pg_get_serial_sequence('accounts_studentsubject', 'id'),
                    COALESCE((SELECT MAX(id) FROM accounts_studentsubject), 0) + 1,
                    false
                )
            """)

    # 1. Backfill category + is_compulsory on existing subjects.
    for subject in Subject.objects.all():
        changed = False
        if subject.name in COMPULSORY:
            if not subject.is_compulsory:
                subject.is_compulsory = True
                changed = True
            if subject.category != 'CORE':
                subject.category = 'CORE'
                changed = True
        else:
            new_cat = category_for(subject.name)
            if subject.category != new_cat:
                subject.category = new_cat
                changed = True
        if changed:
            subject.save(update_fields=['is_compulsory', 'category'])

    # 2. Make sure every Class has the 4 compulsory subjects.
    for klass in Class.objects.all():
        for name, code in COMPULSORY.items():
            try:
                subject = Subject.objects.get(code=f'{code}-{klass.id}')
                updates = []
                if subject.assigned_class_id != klass.id:
                    subject.assigned_class = klass
                    updates.append('assigned_class')
                if not subject.is_compulsory:
                    subject.is_compulsory = True
                    updates.append('is_compulsory')
                if subject.category != 'CORE':
                    subject.category = 'CORE'
                    updates.append('category')
                if updates:
                    subject.save(update_fields=updates)
            except Subject.DoesNotExist:
                Subject.objects.create(
                    code=f'{code}-{klass.id}',
                    name=name,
                    assigned_class=klass,
                    is_compulsory=True,
                    category='CORE',
                )

    # 3. Assign every compulsory subject to every existing student.
    compulsory_subjects = list(Subject.objects.filter(is_compulsory=True))
    for student in Student.objects.all():
        for subject in compulsory_subjects:
            StudentSubject.objects.get_or_create(
                student=student,
                subject=subject,
                defaults={'is_elective': False},
            )


def backward(apps, schema_editor):
    """Reversal intentionally does NOT delete StudentSubject rows or
    un-flag is_compulsory. The schema migration itself will drop the
    StudentSubject table and the is_compulsory column."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_subject_categories_student_subject'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
