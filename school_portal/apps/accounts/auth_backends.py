"""Authentication backend that allows students to log in using their Student ID."""
import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class StudentIDAuthBackend(ModelBackend):
    """Authenticate a student by their Student ID.

    Looks up the Student model by student_id, retrieves the associated
    User, and verifies the password.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        from .models import Student

        try:
            student = Student.objects.select_related("user").get(
                student_id__iexact=username.strip()
            )
        except Student.DoesNotExist:
            return None

        user = student.user
        if user.check_password(password) and self.user_can_authenticate(user):
            logger.debug(
                "StudentIDAuthBackend: user %s authenticated via student_id %s",
                user.username,
                student.student_id,
            )
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
