from django.core.management.base import BaseCommand
from apps.accounts.models import AcademicTerm, SubjectRegistration, StudentSubject, Subject, Student


class Command(BaseCommand):
    help = 'Create initial AcademicTerm and migrate existing StudentSubject data into SubjectRegistration.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--term', default='1st',
            choices=['1st', '2nd', '3rd'],
            help='Term to create (default: 1st)',
        )
        parser.add_argument(
            '--session', default='2025-2026',
            help='Session (default: 2025-2026)',
        )

    def handle(self, *args, **options):
        term_code = options['term']
        session = options['session']

        term, created = AcademicTerm.objects.get_or_create(
            term=term_code,
            session=session,
            defaults={'is_active': True, 'registration_open': True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created term: {term.name}'))
        else:
            term.is_active = True
            term.registration_open = True
            term.save()
            self.stdout.write(self.style.WARNING(f'Using existing term: {term.name}'))

        # Deactivate other terms
        AcademicTerm.objects.exclude(pk=term.pk).update(is_active=False)

        # Migrate StudentSubject records into SubjectRegistration
        ss_count = StudentSubject.objects.count()
        migrated = 0
        for ss in StudentSubject.objects.select_related('student', 'subject').iterator():
            _, created = SubjectRegistration.objects.get_or_create(
                student=ss.student,
                subject=ss.subject,
                term=term,
            )
            if created:
                migrated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Migrated {migrated}/{ss_count} StudentSubject records into {term.name}.'
            )
        )

        # Also register compulsory subjects for students who have none yet
        students_with_reg = set(
            SubjectRegistration.objects.filter(term=term)
            .values_list('student_id', flat=True)
        )
        compulsory_ids = list(
            Subject.objects.filter(is_compulsory=True).values_list('id', flat=True)
        )
        extras = 0
        for student in Student.objects.exclude(pk__in=students_with_reg):
            for sid in compulsory_ids:
                _, created = SubjectRegistration.objects.get_or_create(
                    student=student, subject_id=sid, term=term,
                )
                if created:
                    extras += 1

        if extras:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Registered {extras} compulsory subjects for students without registrations.'
                )
            )

        self.stdout.write(self.style.SUCCESS('Done.'))
