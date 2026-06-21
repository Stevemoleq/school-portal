from django.apps import AppConfig
from django.db.models.signals import post_save


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        # Auto-assign compulsory subjects to every newly created Student.
        # This is a safety net for any code path that creates a Student
        # (registration form, admin, import, fixtures, shell, etc.).
        from .models import Student

        def _ensure_compulsory(sender, instance, created, **kwargs):
            if not created or not instance.pk:
                return
            try:
                instance.assign_compulsory_subjects()
            except Exception:
                # Never block the save if subject assignment fails
                pass

        post_save.connect(
            _ensure_compulsory,
            sender=Student,
            dispatch_uid='accounts_student_compulsory_subjects',
        )