from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import Student
from apps.parents.models import StudentInvoice, FeeStructure
from decimal import Decimal


class Command(BaseCommand):
    help = "Generate StudentInvoice records for all fee structures and active students."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fee-structure", type=int, default=None,
            help="PK of a specific FeeStructure to generate invoices for (default: all).",
        )

    def handle(self, *args, **options):
        qs = FeeStructure.objects.all()
        if options["fee_structure"]:
            qs = qs.filter(pk=options["fee_structure"])
            if not qs.exists():
                raise CommandError(f"No FeeStructure with pk={options['fee_structure']} found.")

        total_created = 0
        for fs in qs:
            students = Student.objects.select_related("user", "current_class").filter(
                user__is_active=True
            )
            if fs.target_class_id:
                students = students.filter(current_class=fs.target_class)

            created = 0
            for student in students:
                _, was_created = StudentInvoice.objects.get_or_create(
                    student=student,
                    fee_structure=fs,
                    defaults={
                        "total_amount": fs.amount,
                        "paid_amount": Decimal("0.00"),
                        "balance": fs.amount,
                        "status": "unpaid",
                    },
                )
                if was_created:
                    created += 1

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created {created} invoice(s) for fee structure '{fs.name}' ({fs.session})"
                    )
                )
            else:
                self.stdout.write(
                    f"All students already have invoices for fee structure '{fs.name}'."
                )
            total_created += created

        self.stdout.write(self.style.SUCCESS(f"\nDone. {total_created} total invoice(s) created."))
