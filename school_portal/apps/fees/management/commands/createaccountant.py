"""Management command to create a user with the Accountant role.

Usage::

    python manage.py createaccountant --username=jane --password=secret --email=jane@school.com
    python manage.py createaccountant --username=jane --password=secret --first-name=Jane --last-name=Doe
"""
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import StaffProfile
from apps.fees.decorators import get_or_create_accountant_group
from apps.fees.models import Accountant


class Command(BaseCommand):
    help = "Create a new user with the Accountant role and an Accountant profile."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--phone", default="")
        parser.add_argument("--staff", action="store_true",
                            help="Also create a StaffProfile so they appear in the staff list.")
        parser.add_argument("--update", action="store_true",
                            help="Update the user if it already exists.")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        first = options["first_name"]
        last = options["last_name"]
        phone = options["phone"]
        update = options["update"]

        # Validate password against Django validators
        dummy_user = User(username=username, first_name=first, last_name=last)
        try:
            validate_password(password, user=dummy_user)
        except ValidationError as e:
            raise CommandError(
                "Password validation failed:\n" + "\n".join(e.messages)
            )

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "first_name": first, "last_name": last},
        )

        if not created:
            if not update:
                raise CommandError(
                    f"User '{username}' already exists. Use --update to modify."
                )
            user.email = email or user.email
            user.first_name = first or user.first_name
            user.last_name = last or user.last_name
            user.save()

        user.set_password(password)
        user.is_staff = False
        user.save()

        # Make sure they're in the Accountant group
        group = get_or_create_accountant_group()
        user.groups.add(group)
        user.save()

        # Create or update Accountant profile (signal auto-handles group)
        accountant, _ = Accountant.objects.get_or_create(
            user=user,
            defaults={"phone": phone},
        )
        if phone and accountant.phone != phone:
            accountant.phone = phone
            accountant.save()

        # Optionally create StaffProfile
        if options["staff"]:
            StaffProfile.objects.get_or_create(user=user)

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} accountant '{username}' "
            f"({accountant.accountant_id})."
        ))
