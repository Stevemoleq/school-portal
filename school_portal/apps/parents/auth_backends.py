import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

logger = logging.getLogger(__name__)


class ParentPhoneAuthBackend(ModelBackend):
    """
    Custom authentication backend that allows parents to log in using
    their phone number or parent ID instead of username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        username = username.strip()

        try:
            from apps.parents.models import Parent

            parent = Parent.objects.select_related('user').filter(
                Q(phone_number=username) | Q(parent_id__iexact=username)
            ).first()

            if parent and parent.user.check_password(password):
                logger.info(
                    f"Parent authenticated via phone/Parent ID: {parent.parent_id}"
                )
                return parent.user

        except Exception as e:
            logger.error(f"Parent authentication error: {e}", exc_info=True)
            return None

        return None

    def get_user(self, user_id):
        try:
            return User.objects.select_related('parent').get(pk=user_id)
        except User.DoesNotExist:
            return None
