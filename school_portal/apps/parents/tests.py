from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.accounts.models import Class, Student
from apps.results.models import Result
from apps.announcements.models import Announcement
from apps.announcements.forms import AnnouncementForm
from apps.parents.models import (
    Parent, ParentStudentRelationship, Attendance,
    ParentNotification, ParentAnnouncementRead
)
from apps.parents.forms import ParentProfileForm, AdminParentCreateForm
from apps.parents.auth_backends import ParentPhoneAuthBackend


class ParentModelTest(TestCase):
    """Test the Parent model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='parent_test',
            first_name='John',
            last_name='Doe',
            password='testpass123',
        )

    def test_create_parent(self):
        parent = Parent.objects.create(
            user=self.user,
            phone_number='0991234567',
            relationship='father',
        )
        self.assertTrue(parent.parent_id)
        self.assertTrue(parent.parent_id.startswith('PAR-'))
        self.assertEqual(parent.phone_number, '0991234567')
        self.assertEqual(parent.relationship, 'father')
        self.assertEqual(parent.get_relationship_display_name(), 'Father')

    def test_parent_auto_generates_id(self):
        p1 = Parent.objects.create(
            user=self.user, phone_number='0991111111'
        )
        p2_user = User.objects.create_user(
            username='parent_test2', password='testpass123'
        )
        p2 = Parent.objects.create(
            user=p2_user, phone_number='0992222222'
        )
        self.assertNotEqual(p1.parent_id, p2.parent_id)
        self.assertRegex(p1.parent_id, r'^PAR-\d{4}$')

    def test_phone_number_validation(self):
        parent = Parent(
            user=self.user, phone_number='invalid'
        )
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_phone_number_unique(self):
        Parent.objects.create(
            user=self.user, phone_number='0991234567'
        )
        user2 = User.objects.create_user(
            username='parent2', password='testpass123'
        )
        with self.assertRaises(Exception):
            Parent.objects.create(
                user=user2, phone_number='0991234567'
            )

    def test_children_property(self):
        parent = Parent.objects.create(
            user=self.user, phone_number='0991234567'
        )
        cls = Class.objects.create(name='Form 1')
        stu_user = User.objects.create_user(
            username='NZS-26-F1-0001', password='test123'
        )
        student = Student.objects.create(
            user=stu_user,
            student_id='NZS-26-F1-0001',
            registration_number='NZS-26-F1-0001',
            current_class=cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        ParentStudentRelationship.objects.create(
            parent=parent, student=student
        )
        self.assertEqual(parent.children_count, 1)
        self.assertIn(student, parent.children)


class ParentStudentRelationshipTest(TestCase):
    """Test the Parent-Student relationship."""

    def setUp(self):
        self.cls = Class.objects.create(name='Form 1')
        self.parent_user = User.objects.create_user(
            username='parent1', password='test123'
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0991234567'
        )
        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0002', password='test123'
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0002',
            registration_number='NZS-26-F1-0002',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )

    def test_create_relationship(self):
        rel = ParentStudentRelationship.objects.create(
            parent=self.parent,
            student=self.student,
            is_primary_contact=True,
        )
        self.assertEqual(rel.parent, self.parent)
        self.assertEqual(rel.student, self.student)
        self.assertTrue(rel.is_primary_contact)

    def test_unique_relationship(self):
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )
        with self.assertRaises(Exception):
            ParentStudentRelationship.objects.create(
                parent=self.parent, student=self.student
            )

    def test_one_parent_multiple_children(self):
        """Test that a parent can have multiple children."""
        stu_user2 = User.objects.create_user(
            username='NZS-26-F1-0003', password='test123'
        )
        student2 = Student.objects.create(
            user=stu_user2,
            student_id='NZS-26-F1-0003',
            registration_number='NZS-26-F1-0003',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=student2
        )
        self.assertEqual(self.parent.children_count, 2)

    def test_one_student_multiple_parents(self):
        """Test that a student can have multiple parents."""
        parent_user2 = User.objects.create_user(
            username='parent2', password='test123'
        )
        parent2 = Parent.objects.create(
            user=parent_user2, phone_number='0997654321'
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )
        ParentStudentRelationship.objects.create(
            parent=parent2, student=self.student
        )
        self.assertEqual(
            self.student.parent_relationships.count(), 2
        )


class AttendanceModelTest(TestCase):
    """Test the Attendance model."""

    def setUp(self):
        self.cls = Class.objects.create(name='Form 1')
        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0004', password='test123'
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0004',
            registration_number='NZS-26-F1-0004',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        self.teacher_user = User.objects.create_user(
            username='teacher1', password='test123', is_staff=True
        )

    def test_create_attendance(self):
        from datetime import date
        att = Attendance.objects.create(
            student=self.student,
            date=date.today(),
            status='present',
            term='1st',
            session='2025-2026',
            recorded_by=self.teacher_user,
        )
        self.assertEqual(att.status, 'present')
        self.assertEqual(att.student, self.student)

    def test_attendance_unique(self):
        from datetime import date
        Attendance.objects.create(
            student=self.student,
            date=date.today(),
            status='present',
            term='1st',
            session='2025-2026',
        )
        with self.assertRaises(Exception):
            Attendance.objects.create(
                student=self.student,
                date=date.today(),
                status='absent',
                term='1st',
                session='2025-2026',
            )

    def test_student_summary(self):
        from datetime import date, timedelta
        # Create 5 attendance records: 3 present, 1 absent, 1 late
        for i in range(3):
            Attendance.objects.create(
                student=self.student,
                date=date.today() - timedelta(days=i),
                status='present',
                term='1st',
                session='2025-2026',
            )
        Attendance.objects.create(
            student=self.student,
            date=date.today() - timedelta(days=3),
            status='absent',
            term='1st',
            session='2025-2026',
        )
        Attendance.objects.create(
            student=self.student,
            date=date.today() - timedelta(days=4),
            status='late',
            term='1st',
            session='2025-2026',
        )

        summary = Attendance.get_student_summary(
            self.student, term='1st', session='2025-2026'
        )
        self.assertEqual(summary['total'], 5)
        self.assertEqual(summary['present'], 3)
        self.assertEqual(summary['absent'], 1)
        self.assertEqual(summary['late'], 1)
        self.assertEqual(summary['percentage'], 60.0)


class ParentAuthenticationTest(TestCase):
    """Test parent authentication with phone number and Parent ID."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='parent_test_auth',
            first_name='Alice',
            last_name='Banda',
            password='securepass123',
        )
        self.parent = Parent.objects.create(
            user=self.user,
            phone_number='0998887777',
            relationship='mother',
        )

    def test_login_with_phone_number(self):
        response = self.client.post(reverse('parent_login'), {
            'login_id': '0998887777',
            'password': 'securepass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.id
        )

    def test_login_with_parent_id(self):
        response = self.client.post(reverse('parent_login'), {
            'login_id': self.parent.parent_id,
            'password': 'securepass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.id
        )

    def test_login_with_wrong_password(self):
        response = self.client.post(reverse('parent_login'), {
            'login_id': '0998887777',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_authenticated_parent_redirected_away_from_login(self):
        self.client.login(
            username='parent_test_auth', password='securepass123'
        )
        response = self.client.get(reverse('parent_login'))
        self.assertIn(response.status_code, [301, 302])

    def test_dashboard_redirect_for_parent(self):
        """Test that dashboard_redirect sends parents to parent_dashboard."""
        self.client.login(
            username='parent_test_auth', password='securepass123'
        )
        response = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(
            response, reverse('parent_dashboard')
        )


class ParentDashboardTest(TestCase):
    """Test the parent dashboard view."""

    def setUp(self):
        self.client = Client()
        self.cls = Class.objects.create(name='Form 1')

        self.parent_user = User.objects.create_user(
            username='parent_dash',
            first_name='Bob',
            password='testpass123',
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0991112222',
            relationship='father',
        )

        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0005', password='test123',
            first_name='Child', last_name='One',
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0005',
            registration_number='NZS-26-F1-0005',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('parent_dashboard'))
        self.assertIn(response.status_code, [301, 302])

    def test_dashboard_shows_children(self):
        self.client.login(
            username='parent_dash', password='testpass123'
        )
        response = self.client.get(reverse('parent_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'parents/parent_dashboard.html'
        )
        self.assertContains(response, 'Child')
        self.assertContains(response, 'NZS-26-F1-0005')

    def test_non_parent_cannot_access_dashboard(self):
        """Test that student/teacher users cannot access parent dashboard."""
        self.client.login(
            username='NZS-26-F1-0005', password='test123'
        )
        response = self.client.get(reverse('parent_dashboard'))
        # Should redirect away from parent dashboard
        self.assertIn(response.status_code, [301, 302])


class ParentViewResultsTest(TestCase):
    """Test that parents can view their children's results."""

    def setUp(self):
        self.client = Client()
        self.cls = Class.objects.create(name='Form 1')
        from apps.accounts.models import Subject
        self.subject = Subject.objects.create(
            name='Mathematics', code='MATH',
            assigned_class=self.cls,
        )

        self.parent_user = User.objects.create_user(
            username='parent_results',
            first_name='Grace',
            password='testpass123',
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0993334444',
            relationship='mother',
        )

        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0006', password='test123',
            first_name='Study', last_name='Child',
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0006',
            registration_number='NZS-26-F1-0006',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )

        # Create a published result
        Result.objects.create(
            student=self.student,
            subject=self.subject,
            marks=85,
            term='1st',
            session='2025-2026',
            is_published=True,
        )

    def test_parent_can_view_child_results(self):
        self.client.login(
            username='parent_results', password='testpass123'
        )
        url = reverse(
            'parent_child_results',
            args=[self.student.student_id]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mathematics')
        self.assertContains(response, '85')

    def test_parent_cannot_view_unlinked_student(self):
        """Test that a parent cannot view results for a student they are not linked to."""
        other_stu_user = User.objects.create_user(
            username='NZS-26-F1-0007', password='test123',
        )
        other_student = Student.objects.create(
            user=other_stu_user,
            student_id='NZS-26-F1-0007',
            registration_number='NZS-26-F1-0007',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        self.client.login(
            username='parent_results', password='testpass123'
        )
        url = reverse(
            'parent_child_results',
            args=[other_student.student_id]
        )
        response = self.client.get(url)
        self.assertIn(response.status_code, [301, 302])


class ParentViewAttendanceTest(TestCase):
    """Test that parents can view their children's attendance."""

    def setUp(self):
        self.client = Client()
        self.cls = Class.objects.create(name='Form 1')
        from datetime import date

        self.parent_user = User.objects.create_user(
            username='parent_att',
            first_name='Henry',
            password='testpass123',
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0995556666',
        )

        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0008', password='test123',
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0008',
            registration_number='NZS-26-F1-0008',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )
        ParentStudentRelationship.objects.create(
            parent=self.parent, student=self.student
        )

        Attendance.objects.create(
            student=self.student,
            date=date.today(),
            status='present',
            term='1st',
            session='2025-2026',
        )

    def test_parent_can_view_child_attendance(self):
        self.client.login(
            username='parent_att', password='testpass123'
        )
        url = reverse(
            'parent_child_attendance',
            args=[self.student.student_id]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'parents/child_attendance.html'
        )


class ParentAnnouncementTest(TestCase):
    """Test that parents can view announcements."""

    def setUp(self):
        self.client = Client()
        self.parent_user = User.objects.create_user(
            username='parent_ann',
            first_name='Ivy',
            password='testpass123',
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0997778888',
        )

        self.admin_user = User.objects.create_user(
            username='admin_ann', password='admin123',
            is_staff=True,
        )
        self.announcement = Announcement.objects.create(
            title='School Holiday',
            content='School will be closed.',
            author=self.admin_user,
            target_audience='all',
        )

    def test_parent_can_view_announcements(self):
        self.client.login(
            username='parent_ann', password='testpass123'
        )
        response = self.client.get(reverse('parent_announcements'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'School Holiday')

    def test_announcement_marked_as_read(self):
        self.client.login(
            username='parent_ann', password='testpass123'
        )
        response = self.client.get(
            reverse(
                'parent_announcement_detail',
                args=[self.announcement.pk]
            )
        )
        self.assertEqual(response.status_code, 200)

        # Check it was marked as read
        self.assertTrue(
            ParentAnnouncementRead.objects.filter(
                parent=self.parent,
                announcement=self.announcement,
            ).exists()
        )


class ParentNotificationTest(TestCase):
    """Test the notification system."""

    def setUp(self):
        self.parent_user = User.objects.create_user(
            username='parent_notif', password='testpass123'
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0999990000',
        )

    def test_create_notification(self):
        notification = ParentNotification.objects.create(
            parent=self.parent,
            title='Test Notification',
            message='This is a test.',
            notification_type='in_app',
        )
        self.assertEqual(notification.status, 'sent')
        self.assertIsNotNone(notification.sent_at)

    def test_mark_notification_as_read(self):
        notification = ParentNotification.objects.create(
            parent=self.parent,
            title='Read Test',
            message='Mark as read.',
        )
        notification.mark_as_read()
        self.assertEqual(notification.status, 'read')
        self.assertIsNotNone(notification.read_at)

    def test_mark_notification_as_sent(self):
        notification = ParentNotification.objects.create(
            parent=self.parent,
            title='Sent Test',
            message='Mark as sent.',
        )
        notification.mark_as_sent()
        self.assertEqual(notification.status, 'sent')
        self.assertIsNotNone(notification.sent_at)


class AdminParentCreateFormTest(TestCase):
    """Test the admin form for creating parents."""

    def setUp(self):
        self.cls = Class.objects.create(name='Form 1')
        self.stu_user = User.objects.create_user(
            username='NZS-26-F1-0010', password='test123'
        )
        self.student = Student.objects.create(
            user=self.stu_user,
            student_id='NZS-26-F1-0010',
            registration_number='NZS-26-F1-0010',
            current_class=self.cls,
            admission_year=2026,
            admission_form='Form 1',
        )

    def test_create_parent_with_form(self):
        form = AdminParentCreateForm(data={
            'first_name': 'Test',
            'last_name': 'Parent',
            'phone_number': '0881234567',
            'relationship': 'father',
        })
        self.assertTrue(form.is_valid(), form.errors.as_data())
        parent = form.save(student=self.student)
        self.assertTrue(parent.parent_id.startswith('PAR-'))
        self.assertEqual(parent.phone_number, '0881234567')
        self.assertEqual(
            parent.student_relationships.count(), 1
        )

    def test_duplicate_phone_rejected(self):
        parent_user = User.objects.create_user(
            username='dup_parent', password='test123'
        )
        Parent.objects.create(
            user=parent_user, phone_number='0881234567'
        )
        form = AdminParentCreateForm(data={
            'first_name': 'Dup',
            'last_name': 'Parent',
            'phone_number': '0881234567',
            'relationship': 'mother',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)


class SecurityRestrictionTest(TestCase):
    """Test security restrictions for parent accounts."""

    def setUp(self):
        self.client = Client()
        self.cls = Class.objects.create(name='Form 1')
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True
        )

        self.parent_user = User.objects.create_user(
            username='parent_sec', password='testpass123'
        )
        self.parent = Parent.objects.create(
            user=self.parent_user, phone_number='0994445555',
        )

        self.teacher_user = User.objects.create_user(
            username='teacher_sec', password='test123'
        )

    def test_parent_cannot_access_admin_dashboard(self):
        self.client.login(
            username='parent_sec', password='testpass123'
        )
        response = self.client.get(reverse('admin_dashboard'))
        self.assertNotEqual(response.status_code, 200)
        # Should be redirected
        self.assertIn(response.status_code, [301, 302])

    def test_parent_cannot_access_teacher_dashboard(self):
        self.client.login(
            username='parent_sec', password='testpass123'
        )
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertIn(response.status_code, [301, 302])

    def test_parent_cannot_access_student_results(self):
        self.client.login(
            username='parent_sec', password='testpass123'
        )
        response = self.client.get(reverse('student_results'))
        self.assertIn(response.status_code, [301, 302])

    def test_parent_cannot_access_admin_panel(self):
        self.client.login(
            username='parent_sec', password='testpass123'
        )
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, [301, 302])

    def test_parent_cannot_manage_results(self):
        self.client.login(
            username='parent_sec', password='testpass123'
        )
        from apps.accounts.models import Subject
        subject = Subject.objects.create(
            name='Test', code='TST', assigned_class=self.cls
        )
        response = self.client.get(
            reverse('manage_results', args=[subject.id])
        )
        self.assertNotEqual(response.status_code, 200)
