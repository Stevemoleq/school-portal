"""
Seed elective subjects for all classes.

Creates standard Science, Humanities, Commercial, and Technical subjects
for every class that doesn't already have them.
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import Subject, Class


ELECTIVE_SUBJECTS = [
    # (name, code_suffix)
    ('Physics', 'PHY'),
    ('Chemistry', 'CHEM'),
    ('Agriculture', 'AGR'),
    ('Computer Studies', 'CS'),
    ('History', 'HIST'),
    ('Geography', 'GEOG'),
    ('Bible Knowledge', 'BK'),
    ('Commerce', 'COMM'),
    ('Accounting', 'ACCT'),
    ('Economics', 'ECON'),
    ('Technical Drawing', 'TD'),
]


class Command(BaseCommand):
    help = 'Create elective subjects for all classes.'

    def handle(self, *args, **options):
        created = 0
        for cls in Class.objects.all():
            # Extract the form number from the class name
            class_num = ''.join(c for c in cls.name if c.isdigit())
            if not class_num:
                class_num = str(cls.id)

            for name, code_prefix in ELECTIVE_SUBJECTS:
                code = f'{code_prefix}-{class_num}'
                subj, is_new = Subject.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'assigned_class': cls,
                    },
                )
                if is_new:
                    # The save() hook auto-categorizes by name
                    subj.save()
                    created += 1
                    self.stdout.write(f'  Created {code} ({name}) for {cls.name}')
                elif subj.assigned_class_id != cls.id:
                    subj.assigned_class = cls
                    subj.save(update_fields=['assigned_class'])

        self.stdout.write(self.style.SUCCESS(f'Created {created} new elective subjects.'))
