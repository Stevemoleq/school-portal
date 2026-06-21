from django.apps import AppConfig


class ParentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parents'
    verbose_name = 'Parent/Guardian Portal'

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
