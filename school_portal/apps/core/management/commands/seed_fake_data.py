"""Seed the database with realistic fake data for development/testing.

Usage::

    python manage.py seed_fake_data
    python manage.py seed_fake_data --clear   # wipe existing data first
"""
import random
import secrets
from datetime import date, timedelta, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import (
    Class, Subject, Student, Teacher, StudentSubject,
    AcademicTerm, SubjectRegistration,
)
from apps.parents.models import (
    Parent, ParentStudentRelationship, Attendance,
    FeeStructure, StudentInvoice, BankPaymentReceipt,
)
from apps.results.models import Result
from apps.fees.models import Accountant, Receipt, FeeConfiguration
from apps.announcements.models import Announcement


FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard",
    "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin",
]
FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Betty", "Margaret",
    "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily", "Donna", "Michelle",
]
LAST_NAMES = [
    "Banda", "Chimwemwe", "Daka", "Gondwe", "Kamanga", "Khoviwa",
    "Lungu", "Mhango", "Mkandawire", "Mwale", "Nkhoma", "Nyirenda",
    "Phiri", "Tembwe", "Zulu", "Moyo", "Chirwa", "Gwaza", "Jere",
    "Kachingwe", "Mandevu", "Chipofya", "Bwalya", "Chilundika",
]

BANKS = ["nbm", "standard", "nbs", "fdh", "fcb", "ecobank"]
BANK_NAMES_MAP = {
    "nbm": "National Bank of Malawi",
    "standard": "Standard Bank",
    "nbs": "NBS Bank",
    "fdh": "FDH Bank",
    "fcb": "First Capital Bank",
    "ecobank": "EcoBank",
}


class Command(BaseCommand):
    help = "Seed the database with realistic fake data for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete all existing data before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Attendance.objects.all().delete()
            BankPaymentReceipt.objects.all().delete()
            Receipt.objects.all().delete()
            StudentInvoice.objects.all().delete()
            FeeStructure.objects.all().delete()
            Result.objects.all().delete()
            SubjectRegistration.objects.all().delete()
            StudentSubject.objects.all().delete()
            ParentStudentRelationship.objects.all().delete()
            Parent.objects.all().delete()
            Student.objects.all().delete()
            Teacher.objects.all().delete()
            Accountant.objects.all().delete()
            Announcement.objects.all().delete()
            Subject.objects.all().delete()
            Class.objects.all().delete()
            AcademicTerm.objects.all().delete()
            FeeConfiguration.objects.all().delete()
            # Delete non-superuser, non-admin users
            User.objects.filter(is_superuser=False, is_staff=False).delete()
            self.stdout.write(self.style.WARNING("All data cleared."))

        self.stdout.write("Seeding fake data...")

        # ── 1. Classes ──
        classes_data = [
            ("Form 1A", "A"), ("Form 1B", "B"),
            ("Form 2A", "A"), ("Form 2B", "B"),
            ("Form 3A", "A"), ("Form 3B", "B"),
            ("Form 4A", "A"),
        ]
        classes = []
        for name, section in classes_data:
            cls, _ = Class.objects.get_or_create(
                name=name,
                defaults={"section": section},
            )
            classes.append(cls)
        self.stdout.write(f"  Created {len(classes)} classes")

        # ── 2. Subjects ──
        subjects_data = [
            ("English", "ENG", "CORE", True),
            ("Mathematics", "MATH", "CORE", True),
            ("Chichewa", "CHIC", "CORE", True),
            ("Biology", "BIO", "CORE", True),
            ("Physics", "PHY", "SCIENCE", False),
            ("Chemistry", "CHEM", "SCIENCE", False),
            ("Geography", "GEO", "HUMANITIES", False),
            ("History", "HIST", "HUMANITIES", False),
            ("Commerce", "COM", "COMMERCIAL", False),
            ("Computer Studies", "CS", "TECHNICAL", False),
            ("Agriculture", "AGRI", "TECHNICAL", False),
            ("Life Skills", "LS", "OTHER", False),
        ]
        subjects = []
        for name, code, cat, comp in subjects_data:
            sub, _ = Subject.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "assigned_class": random.choice(classes),
                    "category": cat,
                    "is_compulsory": comp,
                },
            )
            subjects.append(sub)
        self.stdout.write(f"  Created {len(subjects)} subjects")

        # ── 3. Academic Terms ──
        terms = []
        for session in ["2025-2026", "2026-2027"]:
            for term_code in ["1st", "2nd", "3rd"]:
                term, _ = AcademicTerm.objects.get_or_create(
                    term=term_code,
                    session=session,
                    defaults={
                        "is_active": session == "2026-2027" and term_code == "1st",
                        "registration_open": session == "2026-2027" and term_code == "1st",
                    },
                )
                terms.append(term)
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        self.stdout.write(f"  Created {len(terms)} academic terms (active: {active_term})")

        # ── 4. Admin User ──
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@nazareneschool.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123!")
            admin_user.save()
            self.stdout.write("  Created admin user (username: admin, password: admin123!)")
        else:
            admin_user.set_password("admin123!")
            admin_user.save()
            self.stdout.write("  Updated admin user password to: admin123!")

        # ── 5. Users & Students ──
        existing_count = Student.objects.count()
        students = list(Student.objects.all())
        needed = max(0, 20 - existing_count)
        for i in range(needed):
            first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
            last = random.choice(LAST_NAMES)
            username = f"stu_{secrets.token_urlsafe(8)}"
            user = User.objects.create_user(
                username=username,
                password="student123!",
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}@example.com",
            )
            cls = random.choice(classes)
            form = cls.name.replace("A", "").replace("B", "").strip()
            student = Student.objects.create(
                user=user,
                admission_year=2026,
                admission_form=form,
                current_class=cls,
                date_of_birth=date(random.randint(2008, 2014), random.randint(1, 12), random.randint(1, 28)),
                address=f"PO Box {random.randint(100, 9999)}, Lilongwe, Malawi",
            )
            students.append(student)
        self.stdout.write(f"  {Student.objects.count()} students (password: student123!)")

        # ── 6. Teachers ──
        teachers = list(Teacher.objects.all())
        teacher_subjects = [
            ("ENG", ["English"]),
            ("MATH", ["Mathematics"]),
            ("CHIC", ["Chichewa"]),
            ("BIO", ["Biology"]),
            ("SCI", ["Physics", "Chemistry"]),
            ("HUM", ["Geography", "History"]),
            ("COM", ["Commerce"]),
            ("TECH", ["Computer Studies", "Agriculture"]),
        ]
        for i, (eid, sub_names) in enumerate(teacher_subjects, 1):
            username = f"TCH-{eid}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "password": "teacher123!",
                    "first_name": random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE),
                    "last_name": random.choice(LAST_NAMES),
                    "email": f"teacher.{eid.lower()}@nazarene.com",
                    "is_staff": False,
                },
            )
            if created:
                user.set_password("teacher123!")
                user.save()
            teacher, _ = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    "employee_id": f"TCH-{eid}",
                    "phone": f"+265{random.randint(900000000, 999999999)}",
                    "date_hired": date(random.randint(2020, 2025), random.randint(1, 12), 1),
                },
            )
            for sn in sub_names:
                sub = Subject.objects.filter(name=sn).first()
                if sub:
                    teacher.subjects.add(sub)
            teachers.append(teacher)
        self.stdout.write(f"  {Teacher.objects.count()} teachers (password: teacher123!)")

        # ── 7. StudentSubject assignments ──
        count = 0
        for student in students:
            # Assign all compulsory subjects
            for sub in Subject.objects.filter(is_compulsory=True):
                ss, created = StudentSubject.objects.get_or_create(
                    student=student, subject=sub,
                    defaults={"is_elective": False},
                )
                if created:
                    count += 1
            # Assign 2-3 electives
            electives = list(Subject.objects.filter(is_compulsory=False))
            for sub in random.sample(electives, min(3, len(electives))):
                ss, created = StudentSubject.objects.get_or_create(
                    student=student, subject=sub,
                    defaults={"is_elective": True},
                )
                if created:
                    count += 1
        self.stdout.write(f"  Created {count} student-subject assignments")

        # ── 8. Subject Registrations (for active term) ──
        if active_term:
            reg_count = 0
            for student in students:
                student_subs = StudentSubject.objects.filter(
                    student=student
                ).values_list("subject_id", flat=True)
                for sub_id in student_subs:
                    _, created = SubjectRegistration.objects.get_or_create(
                        student=student,
                        subject_id=sub_id,
                        term=active_term,
                    )
                    if created:
                        reg_count += 1
            self.stdout.write(f"  Created {reg_count} subject registrations for {active_term}")

        # ── 9. Parents ──
        existing_parents = Parent.objects.count()
        parents = list(Parent.objects.all())
        needed = max(0, 10 - existing_parents)
        relationships = ["father", "mother", "guardian"]
        for i in range(needed):
            first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
            last = random.choice(LAST_NAMES)
            user = User.objects.create_user(
                username=f"parent_{secrets.token_urlsafe(6)}",
                password="parent123!",
                first_name=first,
                last_name=last,
            )
            phone = f"+265{random.randint(900000000, 999999999)}"
            parent = Parent.objects.create(
                user=user,
                phone_number=phone,
                relationship=random.choice(relationships),
            )
            parents.append(parent)
        self.stdout.write(f"  {Parent.objects.count()} parents (password: parent123!)")

        # ── 10. Parent-Student Relationships ──
        rel_count = 0
        for student in students[:10]:
            parent = random.choice(parents[:5])
            _, created = ParentStudentRelationship.objects.get_or_create(
                parent=parent,
                student=student,
                defaults={"is_primary_contact": True},
            )
            if created:
                rel_count += 1
        self.stdout.write(f"  Created {rel_count} parent-student relationships")

        # ── 11. Results ──
        if active_term:
            result_count = 0
            for student in students:
                student_subs = StudentSubject.objects.filter(
                    student=student
                ).select_related("subject")
                for ss in student_subs:
                    marks = round(random.gauss(62, 18), 1)
                    marks = max(0, min(100, marks))
                    Result.objects.get_or_create(
                        student=student,
                        subject=ss.subject,
                        term=active_term.term,
                        session=active_term.session,
                        defaults={
                            "marks": marks,
                            "is_published": random.random() > 0.3,
                        },
                    )
                    result_count += 1
            self.stdout.write(f"  Created {result_count} results for {active_term}")

        # ── 12. Attendance ──
        att_count = 0
        for student in students:
            d = date.today()
            for day_offset in range(20):
                att_date = d - timedelta(days=day_offset)
                if att_date.weekday() >= 5:
                    continue
                status = random.choices(
                    ["present", "absent", "late", "excused"],
                    weights=[75, 10, 10, 5],
                )[0]
                _, created = Attendance.objects.get_or_create(
                    student=student,
                    date=att_date,
                    term=active_term.term if active_term else "1st",
                    session=active_term.session if active_term else "2026-2027",
                    defaults={"status": status},
                )
                if created:
                    att_count += 1
        self.stdout.write(f"  Created {att_count} attendance records")

        # ── 13. Fee Structures ──
        fee_structures = []
        fee_data = [
            ("Term 1 Tuition Fee", 85000, "1st"),
            ("Term 2 Tuition Fee", 85000, "2nd"),
            ("Term 3 Tuition Fee", 85000, "3rd"),
            ("Examination Fee", 15000, "3rd"),
            ("Library Fee", 5000, "1st"),
            ("Sports Fee", 3000, "1st"),
        ]
        for name, amount, term_code in fee_data:
            fs, _ = FeeStructure.objects.get_or_create(
                name=name,
                term=term_code,
                session="2026-2027",
                defaults={"amount": Decimal(str(amount))},
            )
            fee_structures.append(fs)
        self.stdout.write(f"  Created {len(fee_structures)} fee structures")

        # ── 14. Student Invoices ──
        inv_count = 0
        for student in students:
            for fs in random.sample(fee_structures, min(3, len(fee_structures))):
                paid = random.choice([
                    Decimal("0"),
                    fs.amount * Decimal(str(random.choice([0, 0.25, 0.5, 0.75, 1.0]))),
                ])
                StudentInvoice.objects.get_or_create(
                    student=student,
                    fee_structure=fs,
                    defaults={
                        "total_amount": fs.amount,
                        "paid_amount": paid,
                    },
                )
                inv_count += 1
        self.stdout.write(f"  Created {inv_count} student invoices")

        # ── 15. Accountant ──
        acc_user, created = User.objects.get_or_create(
            username="accountant1",
            defaults={
                "first_name": "Grace",
                "last_name": "Mwale",
                "email": "grace.mwale@nazarene.com",
                "is_staff": False,
            },
        )
        acc_user.set_password("account123!")
        acc_user.save()
        accountant, _ = Accountant.objects.get_or_create(
            user=acc_user,
            defaults={"phone": "+265987654321"},
        )
        self.stdout.write(f"  Accountant username=accountant1 password=account123!")

        # ── 16. Bank Payment Receipts ──
        slip_count = 0
        for inv in StudentInvoice.objects.filter(paid_amount__gt=0)[:5]:
            receipt_data = {
                "invoice": inv,
                "student": inv.student,
                "bank_name": random.choice(BANKS),
                "depositor_name": inv.student.user.get_full_name(),
                "transaction_reference": f"TXN-{secrets.token_hex(6).upper()}",
                "amount_paid": inv.paid_amount,
                "payment_date": date.today() - timedelta(days=random.randint(1, 30)),
                "status": "approved",
                "verified_by": acc_user,
                "verified_at": timezone.now(),
            }
            # Create a dummy image file for the deposit slip
            from django.core.files.base import ContentFile
            # Create a 1x1 PNG
            png_data = (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
                b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
                b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
            )
            slip = BankPaymentReceipt(**receipt_data)
            slip.deposit_slip_image.save(
                f"slip_{secrets.token_hex(4)}.png",
                ContentFile(png_data),
                save=False,
            )
            slip.save()
            slip_count += 1
        self.stdout.write(f"  Created {slip_count} bank payment receipts")

        # ── 17. Announcements ──
        announcements_data = [
            ("Welcome Back to School!", "We welcome all students and staff to the new academic term. Please ensure all fees are paid before registration.", "all"),
            ("Sports Day Announcement", "Annual sports day will be held on 15th July. All students are expected to participate.", "students"),
            ("Staff Meeting", "There will be a staff meeting on Monday at 2pm in the staff room.", "teachers"),
            ("Fee Payment Reminder", "Parents are reminded that term 1 fees are due by the end of this month.", "parents"),
            ("Exam Schedule Released", "The mid-term examination schedule has been published. Check your dashboards for details.", "students"),
        ]
        ann_count = 0
        for title, content, audience in announcements_data:
            _, created = Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "content": content,
                    "author": teachers[0].user,
                    "target_audience": audience,
                },
            )
            if created:
                ann_count += 1
        self.stdout.write(f"  Created {ann_count} announcements")

        # ── Summary ──
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("  SEED DATA CREATED SUCCESSFULLY"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"  Classes:              {Class.objects.count()}")
        self.stdout.write(f"  Subjects:             {Subject.objects.count()}")
        self.stdout.write(f"  Students:             {Student.objects.count()}")
        self.stdout.write(f"  Teachers:             {Teacher.objects.count()}")
        self.stdout.write(f"  Parents:              {Parent.objects.count()}")
        self.stdout.write(f"  Academic Terms:       {AcademicTerm.objects.count()}")
        self.stdout.write(f"  Results:              {Result.objects.count()}")
        self.stdout.write(f"  Attendance Records:   {Attendance.objects.count()}")
        self.stdout.write(f"  Fee Structures:       {FeeStructure.objects.count()}")
        self.stdout.write(f"  Student Invoices:     {StudentInvoice.objects.count()}")
        self.stdout.write(f"  Bank Receipts:        {BankPaymentReceipt.objects.count()}")
        self.stdout.write(f"  Announcements:        {Announcement.objects.count()}")
        self.stdout.write("")
        self.stdout.write("  Login credentials:")
        self.stdout.write(f"    Admin:      admin / admin123!")
        self.stdout.write(f"    Accountant: accountant1 / account123!")
        self.stdout.write(f"    Teachers:   TCH-ENG, TCH-MATH, ... / teacher123!")
        self.stdout.write(f"    Students:   (login via Student ID) / student123!")
        self.stdout.write(f"    Parents:    (login via phone number) / parent123!")
        self.stdout.write(self.style.SUCCESS("=" * 50))
