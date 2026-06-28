"""
Create a superuser with a randomly generated, one-time password.

Usage:
    DJANGO_SUPERUSER_PASSWORD=<password> python manage.py create_admin
    python manage.py create_admin --username admin --email admin@example.com

If DJANGO_SUPERUSER_PASSWORD is not set, a strong random password is
generated, printed to stdout, and the operator is expected to rotate
it on first login.
"""
import os
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings


def _generate_random_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Create or update a superuser with a secure password."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
        parser.add_argument("--email", default="admin@example.com", help="Admin email")
        parser.add_argument(
            "--password",
            default=None,
            help="Password. If omitted, DJANGO_SUPERUSER_PASSWORD env var is used; "
                 "otherwise a random one is generated.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Never prompt — fail if password is not explicitly provided.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]

        password = options["password"] or os.environ.get("DJANGO_SUPERUSER_PASSWORD") or getattr(settings, "DJANGO_SUPERUSER_PASSWORD", None)

        if not password:
            if options["noinput"]:
                self.stderr.write(
                    "ERROR: --noinput was passed but no password was provided. "
                    "Set DJANGO_SUPERUSER_PASSWORD or pass --password."
                )
                raise SystemExit(1)
            password = _generate_random_password()
            generated = True
        else:
            generated = False

        if len(password) < 12:
            self.stderr.write("ERROR: Password must be at least 12 characters.")
            raise SystemExit(1)

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Admin user {username} {action}."))
        if generated:
            self.stdout.write(self.style.WARNING("Generated one-time password:"))
            self.stdout.write(password)
            self.stdout.write(
                self.style.WARNING(
                    "Save this password securely — it will not be shown again. "
                    "Rotate it on first login."
                )
            )
