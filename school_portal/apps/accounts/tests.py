from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.accounts.models import Class, Student, Teacher

from apps.accounts.student_id import generate_student_id, get_form_display, get_admission_year_display


class StudentIdGenerationTest(TestCase):
    """Test the student ID generation utility."""

    def setUp(self):
        self.class_obj = Class.objects.create(name="Form 1", section="A")

    def test_generate_basic_id(self):
        sid = generate_student_id(school_code='NZS', admission_year=2026, admission_form='Form 1')
        self.assertTrue(sid.startswith('NZS-26-F1-'))
        self.assertEqual(len(sid), 14)  # NZS-26-F1-0001

    def test_generate_sequential_ids(self):
        # Create students to force different sequences
        user1 = User.objects.create_user(username='test1', email='t1@example.com', password='pass1234')
        Student.objects.create(user=user1, admission_year=2026, admission_form='Form 1', current_class=self.class_obj)
        user2 = User.objects.create_user(username='test2', email='t2@example.com', password='pass1234')
        Student.objects.create(user=user2, admission_year=2026, admission_form='Form 1', current_class=self.class_obj)

        user1.refresh_from_db()
        user2.refresh_from_db()
        s1 = user1.student
        s2 = user2.student
        self.assertNotEqual(s1.student_id, s2.student_id)

    def test_generate_different_forms(self):
        id_f1 = generate_student_id(school_code='NZS', admission_year=2026, admission_form='Form 1')
        id_f2 = generate_student_id(school_code='NZS', admission_year=2026, admission_form='Form 2')
        # Different forms should have independent sequences
        self.assertIn('F1', id_f1)
        self.assertIn('F2', id_f2)

    def test_generate_different_years(self):
        id_26 = generate_student_id(school_code='NZS', admission_year=2026, admission_form='Form 1')
        id_27 = generate_student_id(school_code='NZS', admission_year=2027, admission_form='Form 1')
        self.assertIn('-26-', id_26)
        self.assertIn('-27-', id_27)

    def test_get_form_display(self):
        self.assertEqual(get_form_display('Form 1'), 'F1')
        self.assertEqual(get_form_display('Form 2'), 'F2')
        self.assertEqual(get_form_display('Form 10'), 'F10')
        self.assertEqual(get_form_display('Grade 10'), 'G10')
        self.assertEqual(get_form_display('Senior 1'), 'S1')

    def test_get_admission_year_display(self):
        self.assertEqual(get_admission_year_display(2026), '26')
        self.assertEqual(get_admission_year_display(2099), '99')


class StudentModelTest(TestCase):
    """Test the Student model with auto-generated IDs."""

    def setUp(self):
        self.class_obj = Class.objects.create(name="Form 1", section="A")

    def test_student_auto_generates_id(self):
        user = User.objects.create_user(username='temp', email='temp@example.com', password='pass1234')
        student = Student.objects.create(
            user=user,
            admission_year=2026,
            admission_form='Form 1',
            current_class=self.class_obj,
        )
        self.assertTrue(student.student_id)
        self.assertTrue(student.student_id.startswith('NZS-26-F1-'))
        self.assertEqual(student.registration_number, student.student_id)

    def test_student_id_is_permanent(self):
        user = User.objects.create_user(username='temp', email='temp@example.com', password='pass1234')
        student = Student.objects.create(
            user=user,
            admission_year=2026,
            admission_form='Form 1',
            current_class=self.class_obj,
        )
        original_id = student.student_id

        # "Promote" student to Form 2
        new_class = Class.objects.create(name="Form 2", section="A")
        student.current_class = new_class
        student.save()

        # Student ID should remain the same
        student.refresh_from_db()
        self.assertEqual(student.student_id, original_id)

    def test_student_id_unique_constraint(self):
        user1 = User.objects.create_user(username='temp1', email='t1@example.com', password='pass1234')
        s1 = Student.objects.create(user=user1, admission_year=2026, admission_form='Form 1', current_class=self.class_obj)
        # Force duplicate
        user2 = User.objects.create_user(username='temp2', email='t2@example.com', password='pass1234')
        s2 = Student(user=user2, admission_year=2026, admission_form='Form 1', current_class=self.class_obj)
        s2.student_id = s1.student_id
        with self.assertRaises(Exception):
            s2.save()


class ForceChangePasswordTest(TestCase):
    """Test the force password change flow for new students."""

    def setUp(self):
        self.client = Client()
        self.class_obj = Class.objects.create(name="Form 1", section="A")

    def _create_student(self, must_change=True, password='testpass123'):
        user = User.objects.create_user(
            username='NZS-26-F1-0001',
            email='student@example.com',
            password=password,
            first_name='Test',
            last_name='Student',
        )
        student = Student.objects.create(
            user=user,
            student_id='NZS-26-F1-0001',
            registration_number='NZS-26-F1-0001',
            current_class=self.class_obj,
            admission_year=2026,
            admission_form='Form 1',
            must_change_password=must_change,
        )
        return student

    def test_redirect_to_force_change_after_login(self):
        student = self._create_student(must_change=True)
        self.client.login(username='NZS-26-F1-0001', password='testpass123')
        response = self.client.get(reverse('student_dashboard'))
        self.assertRedirects(response, reverse('force_change_password'))

    def test_can_set_new_password(self):
        student = self._create_student(must_change=True)
        self.client.login(username='NZS-26-F1-0001', password='testpass123')
        response = self.client.post(reverse('force_change_password'), {
            'new_password1': 'newsecurepassword456',
            'new_password2': 'newsecurepassword456',
        })
        self.assertRedirects(response, reverse('student_dashboard'))
        student.refresh_from_db()
        self.assertFalse(student.must_change_password)

    def test_no_redirect_when_not_required(self):
        student = self._create_student(must_change=False)
        self.client.login(username='NZS-26-F1-0001', password='testpass123')
        response = self.client.get(reverse('force_change_password'))
        self.assertRedirects(response, reverse('student_dashboard'))


class UserProfileSettingsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.class_obj = Class.objects.create(name="Form 1", section="A")
        self.user = User.objects.create_user(
            username='NZS-25-F1-0001',
            first_name='Bob',
            last_name='Builder',
            email='bob@example.com',
            password='bobpassword123'
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='NZS-25-F1-0001',
            registration_number='NZS-25-F1-0001',
            current_class=self.class_obj,
            admission_year=2025,
            admission_form='Form 1',
            address='Old Town'
        )
        self.profile_url = reverse('profile')

    def test_profile_view_requires_login(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)

    def test_profile_view_get(self):
        self.client.login(username='NZS-25-F1-0001', password='bobpassword123')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertEqual(response.context['role'], 'student')

    def test_profile_update_details(self):
        self.client.login(username='NZS-25-F1-0001', password='bobpassword123')
        form_data = {
            'action': 'update_profile',
            'first_name': 'Robert',
            'last_name': 'Construction',
            'email': 'robert@example.com',
            'address': 'New Town',
            'date_of_birth': '2008-01-01'
        }
        response = self.client.post(self.profile_url, data=form_data)
        self.assertRedirects(response, self.profile_url)

        self.user.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Robert')
        self.assertEqual(self.user.last_name, 'Construction')
        self.assertEqual(self.user.email, 'robert@example.com')
        self.assertEqual(self.student.address, 'New Town')


class StudentLoginTest(TestCase):
    """Test that students can log in using their Student ID."""

    def setUp(self):
        self.client = Client()
        self.class_obj = Class.objects.create(name="Form 1", section="A")
        self.user = User.objects.create_user(
            username='NZS-26-F1-0001',
            email='student@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Student',
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id='NZS-26-F1-0001',
            registration_number='NZS-26-F1-0001',
            current_class=self.class_obj,
            admission_year=2026,
            admission_form='Form 1',
        )

    def test_login_with_student_id(self):
        response = self.client.post(reverse('login'), {
            'username': 'NZS-26-F1-0001',
            'password': 'testpass123',
        })
        # Login redirects to dashboard_redirect, which redirects to student_dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

    def test_login_with_wrong_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'NZS-26-F1-0001',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)  # stays on login page
