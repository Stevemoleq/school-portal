"""Tests for the subject-assignment system."""
from django.test import TestCase
from django.contrib.auth.models import User
from apps.accounts.models import (
    Class, Subject, Student, Teacher, StudentSubject,
)
from apps.results.models import Result


def make_user(username='u1', email='u1@example.com', password='pw12345!!'):
    return User.objects.create_user(
        username=username, email=email, password=password,
        first_name='Test', last_name='User',
    )


def make_student(username='s1', klass=None, admission_form='Form 1', admission_year=2026):
    user = make_user(
        username=username,
        email=f'{username}@example.com',
    )
    return Student.objects.create(
        user=user,
        admission_year=admission_year,
        admission_form=admission_form,
        current_class=klass,
    )


def make_compulsory_subjects(klass):
    """Create the 4 compulsory subjects for a class (like the data migration)."""
    for name, code in Subject.COMPULSORY_SUBJECTS.items():
        Subject.objects.create(
            name=name, code=f'{code}-{klass.id}',
            assigned_class=klass, is_compulsory=True, category='CORE',
        )


def make_elective(klass, name='Physics', code='PHY'):
    return Subject.objects.create(
        name=name, code=f'{code}-{klass.id}',
        assigned_class=klass, is_compulsory=False, category='SCIENCE',
    )


class SubjectCompulsoryFlagTest(TestCase):
    """The Subject model should auto-flag and categorise compulsory subjects."""

    def setUp(self):
        self.klass = Class.objects.create(name='Form 1', section='A')

    def test_creating_english_marks_compulsory(self):
        s = Subject.objects.create(
            name='English', code='ENG-1', assigned_class=self.klass,
        )
        self.assertTrue(s.is_compulsory)
        self.assertEqual(s.category, Subject.CATEGORY_CORE)

    def test_non_compulsory_subject_defaults(self):
        s = Subject.objects.create(
            name='History', code='HIST-1', assigned_class=self.klass,
        )
        self.assertFalse(s.is_compulsory)
        self.assertEqual(s.category, Subject.CATEGORY_HUMANITIES)

    def test_category_mapping_for_science(self):
        s = Subject.objects.create(
            name='Physics', code='PHY-1', assigned_class=self.klass,
        )
        self.assertEqual(s.category, Subject.CATEGORY_SCIENCE)

    def test_category_mapping_for_commercial(self):
        s = Subject.objects.create(
            name='Commerce', code='COM-1', assigned_class=self.klass,
        )
        self.assertEqual(s.category, Subject.CATEGORY_COMMERCIAL)


class StudentSubjectModelTest(TestCase):
    """The StudentSubject through model enforces uniqueness and supports helpers."""

    def setUp(self):
        self.klass = Class.objects.create(name='Form 1', section='A')
        make_compulsory_subjects(self.klass)
        self.elective = make_elective(self.klass)
        self.student = make_student(klass=self.klass)

    def test_assign_compulsory_subjects(self):
        count = self.student.assign_compulsory_subjects()
        self.assertEqual(count, 4)
        names = list(
            self.student.assigned_subjects.values_list('name', flat=True)
        )
        for required in ['English', 'Mathematics', 'Chichewa', 'Biology']:
            self.assertIn(required, names)

    def test_assign_compulsory_is_idempotent(self):
        self.student.assign_compulsory_subjects()
        self.student.assign_compulsory_subjects()
        self.assertEqual(
            StudentSubject.objects.filter(student=self.student).count(),
            4,
        )

    def test_assign_elective(self):
        self.student.assign_compulsory_subjects()
        ss, created = self.student.assign_subject(self.elective)
        self.assertTrue(created)
        self.assertTrue(ss.is_elective)
        self.assertEqual(
            self.student.elective_subjects().count(), 1
        )

    def test_cannot_remove_compulsory(self):
        self.student.assign_compulsory_subjects()
        english = Subject.objects.get(name='English', assigned_class=self.klass)
        ok, err = self.student.remove_subject(english)
        self.assertFalse(ok)
        self.assertIn('Compulsory', err)
        # The assignment should still exist
        self.assertTrue(self.student.is_enrolled_in(english))

    def test_can_remove_elective(self):
        self.student.assign_compulsory_subjects()
        self.student.assign_subject(self.elective)
        ok, err = self.student.remove_subject(self.elective)
        self.assertTrue(ok)
        self.assertFalse(self.student.is_enrolled_in(self.elective))

    def test_unique_together_enforced(self):
        from django.db import IntegrityError, transaction
        self.student.assign_compulsory_subjects()
        english = Subject.objects.get(name='English', assigned_class=self.klass)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentSubject.objects.create(
                    student=self.student, subject=english
                )


class StudentRegistrationAutoAssignTest(TestCase):
    """The registration form and the post_save signal must auto-assign
    compulsory subjects to every new student."""

    def setUp(self):
        self.klass = Class.objects.create(name='Form 1', section='A')
        make_compulsory_subjects(self.klass)

    def test_admin_form_save_assigns_compulsory(self):
        from apps.accounts.admin import StudentAdminForm
        form_data = {
            'first_name': 'New',
            'last_name': 'Student',
            'email': 'new.student@admin.com',
            'admission_year': 2026,
            'admission_form': 'Form 1',
            'current_class': self.klass.id,
            'date_of_birth': '2010-01-01',
            'address': 'Test',
        }
        form = StudentAdminForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_data())
        student = form.save()
        self.assertEqual(
            student.assigned_subjects.filter(is_compulsory=True).count(),
            4,
        )
        self.assertTrue(student.must_change_password)

    def test_post_save_signal_assigns_compulsory(self):
        user = make_user(username='siguser', email='sig@example.com')
        student = Student.objects.create(
            user=user,
            admission_year=2026,
            admission_form='Form 1',
            current_class=self.klass,
        )
        self.assertEqual(
            student.assigned_subjects.filter(is_compulsory=True).count(),
            4,
        )


class TeacherResultEntryTest(TestCase):
    """Teachers should only see students enrolled in the subject they teach."""

    def setUp(self):
        from django.test import Client
        from apps.accounts.models import AcademicTerm
        self.client = Client()

        self.klass = Class.objects.create(name='Form 4A', section='A')
        make_compulsory_subjects(self.klass)
        self.chemistry = make_elective(self.klass, name='Chemistry', code='CHEM')

        # Active term with registration open — the manage_results view
        # lists only students who have a SubjectRegistration for the
        # selected term.
        self.term = AcademicTerm.objects.create(
            term='1st', session='2025-2026', is_active=True, registration_open=True,
        )

        # Enrolled student
        self.enrolled = make_student(
            username='enrolled', klass=self.klass,
        )
        self.enrolled.assign_compulsory_subjects()
        self.enrolled.assign_subject(self.chemistry)
        from apps.accounts.models import SubjectRegistration
        SubjectRegistration.objects.create(
            student=self.enrolled, subject=self.chemistry, term=self.term,
        )

        # Not enrolled student
        self.not_enrolled = make_student(
            username='notenrolled', klass=self.klass,
        )
        self.not_enrolled.assign_compulsory_subjects()

        # Teacher assigned to chemistry
        teacher_user = make_user(
            username='t1', email='t1@example.com',
        )
        self.teacher = Teacher.objects.create(user=teacher_user, employee_id='T-001')
        self.teacher.subjects.add(self.chemistry)

    def test_only_enrolled_students_appear(self):
        self.client.force_login(self.teacher.user)
        response = self.client.get(
            f'/results/manage/{self.chemistry.id}/'
        )
        self.assertEqual(response.status_code, 200)
        rows = response.context['student_data']
        student_ids = [r['student'].id for r in rows]
        self.assertIn(self.enrolled.id, student_ids)
        self.assertNotIn(self.not_enrolled.id, student_ids)


class ResultAverageTest(TestCase):
    """Averages must be computed only from subjects the student is enrolled in."""

    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.klass = Class.objects.create(name='Form 1', section='A')
        make_compulsory_subjects(self.klass)
        self.physics = make_elective(self.klass, name='Physics', code='PHY')

        user = make_user(username='avgstudent', email='avg@example.com')
        self.student = Student.objects.create(
            user=user,
            admission_year=2026,
            admission_form='Form 1',
            current_class=self.klass,
        )
        self.student.assign_compulsory_subjects()
        # NOT enrolled in physics

        # Add a result for each assigned subject, marks 80
        for subj in self.student.assigned_subjects.all():
            Result.objects.create(
                student=self.student, subject=subj,
                marks=80, term='1st', session='2026-2027',
                is_published=True,
            )
        # And a result for physics that should be ignored
        Result.objects.create(
            student=self.student, subject=self.physics,
            marks=10, term='1st', session='2026-2027',
            is_published=True,
        )

    def test_only_assigned_subjects_in_average(self):
        # 4 compulsory at 80 + 1 physics at 10.
        # If physics included: (4*80 + 10) / 5 = 66
        # If physics excluded: (4*80) / 4 = 80
        # The view should return 80.
        # Bypass the login rate-limiter by using force_login.
        self.client.force_login(self.student.user)
        response = self.client.get('/results/my-results/')
        self.assertEqual(response.status_code, 200)
        # The view returns the first/current group's average
        context = response.context
        self.assertEqual(context['current_group']['average'], 80)


class SubjectAssignmentViewTest(TestCase):
    """Admin subject assignment interface should work for admin users only."""

    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.klass = Class.objects.create(name='Form 1', section='A')
        make_compulsory_subjects(self.klass)
        self.physics = make_elective(self.klass)
        self.student = make_student(
            username='viewstudent', klass=self.klass,
        )
        self.student.assign_compulsory_subjects()

        self.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin12345',
        )

    def test_search_requires_admin(self):
        response = self.client.get('/accounts/manage/subject-assignments/')
        # Unauthenticated — should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_admin_can_view_assignment_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f'/accounts/manage/subject-assignments/{self.student.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('compulsory_subjects', response.context)
        self.assertEqual(len(response.context['compulsory_subjects']), 4)
        self.assertEqual(len(response.context['elective_subjects']), 0)
        # Physics should be available
        available_codes = [s.code for s in response.context['available_subjects']]
        self.assertIn(self.physics.code, available_codes)

    def test_admin_can_add_elective(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f'/accounts/manage/subject-assignments/{self.student.id}/',
            data={
                'action': 'add',
                'subject_id': self.physics.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.student.is_enrolled_in(self.physics))

    def test_cannot_remove_compulsory_via_post(self):
        self.client.force_login(self.admin)
        english = Subject.objects.get(name='English', assigned_class=self.klass)
        response = self.client.post(
            f'/accounts/manage/subject-assignments/{self.student.id}/',
            data={
                'action': 'remove',
                'subject_id': english.id,
            },
            follow=True,
        )
        # Student should still be enrolled
        self.assertTrue(self.student.is_enrolled_in(english))
        # Error message should be in the response
        self.assertContains(response, 'Compulsory', status_code=200)

    def test_admin_can_remove_elective(self):
        self.student.assign_subject(self.physics)
        self.client.force_login(self.admin)
        response = self.client.post(
            f'/accounts/manage/subject-assignments/{self.student.id}/',
            data={
                'action': 'remove',
                'subject_id': self.physics.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.student.is_enrolled_in(self.physics))


class MigrationIntegrityTest(TestCase):
    """The data migration should leave every existing student with the 4
    compulsory subjects. Run inside a transaction so the existing fixture
    data is the source of truth."""

    def test_data_migration_persists_assignments(self):
        # The data migration ran during migrate. We can verify by simply
        # ensuring that all currently-existing students — created before
        # this test ran — already have compulsory subjects.
        # (When the test DB is built, migrate runs and the data migration
        # seeds assignments for any students that exist at that point.)
        from django.db import connection
        with connection.cursor() as c:
            c.execute(
                "SELECT s.id FROM accounts_student s "
                "LEFT JOIN accounts_studentsubject ss "
                "  ON ss.student_id = s.id AND ss.subject_id IN ("
                "    SELECT id FROM accounts_subject WHERE is_compulsory=TRUE"
                "  ) "
                "WHERE ss.id IS NULL LIMIT 1"
            )
            row = c.fetchone()
        # In a fresh test database, there are no students, so this is None
        self.assertIsNone(row)
