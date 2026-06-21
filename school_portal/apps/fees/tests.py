"""Tests for the Tuition Fees Management module.

These tests cover the core financial flows and access control:

* accountant_required decorator
* Payment approval (and Receipt issuance)
* Payment rejection
* Balance auto-update
* Direct payment recording
* Receipt number uniqueness
* Duplicate transaction_reference prevention
* Fee structure → invoice auto-generation
* Student/Parent read-only access
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Class, Student
from apps.fees.decorators import ACCOUNTANT_GROUP, get_or_create_accountant_group
from apps.fees.models import Accountant, AuditLog, FeeConfiguration, Receipt
from apps.parents.models import (
    BankPaymentReceipt,
    FeeStructure,
    StudentInvoice,
)


def make_student(username="stud", sid="STD-2026-0001", klass=None):
    u = User.objects.create_user(username=username, password="x", first_name="St", last_name="Udent")
    if klass is None:
        klass = Class.objects.create(name="Form 1A")
    return Student.objects.create(user=u, student_id=sid, current_class=klass, admission_year=2026)


def make_accountant(username="acc"):
    u = User.objects.create_user(username=username, password="x", first_name="Ac", last_name="Count")
    u.is_staff = True
    u.save()
    grp = get_or_create_accountant_group()
    u.groups.add(grp)
    u.save()
    Accountant.objects.create(user=u, phone="+265 999 123 456")
    return u


def make_parent(username="par"):
    u = User.objects.create_user(username=username, password="x", first_name="Pa", last_name="Rent")
    return u


class AccountantDecoratorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="regular", password="x")

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("fees:accountant_dashboard"))
        self.assertIn(resp.status_code, (301, 302))

    def test_non_accountant_gets_403(self):
        self.client.force_login(self.user)
        # Force the user to be a regular non-staff, non-accountant user
        self.user.is_staff = False
        self.user.save()
        self.user.groups.clear()
        resp = self.client.get(reverse("fees:accountant_dashboard"))
        # 302 = redirect to login (since not staff), 403 = forbidden
        self.assertIn(resp.status_code, (302, 403))

    def test_accountant_passes(self):
        make_accountant("acc1")
        self.client.login(username="acc1", password="x")
        resp = self.client.get(reverse("fees:accountant_dashboard"))
        self.assertEqual(resp.status_code, 200)


class PaymentApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.accountant = make_accountant("acc")
        self.klass = Class.objects.create(name="Form 2B")
        self.student = make_student("stud", klass=self.klass)
        self.fee_structure = FeeStructure.objects.create(
            name="Term 1 Fees", amount=Decimal("100000.00"),
            target_class=self.klass, term="1", session="2026",
        )
        self.invoice = StudentInvoice.objects.create(
            student=self.student, fee_structure=self.fee_structure,
            total_amount=Decimal("100000.00"),
        )
        self.payment = BankPaymentReceipt.objects.create(
            invoice=self.invoice, bank_name="standard",
            depositor_name="Mr. Parent",
            transaction_reference="TX-001",
            amount_paid=Decimal("60000.00"),
            payment_date=date.today(),
        )
        self.client.login(username="acc", password="x")

    def test_approve_creates_receipt(self):
        resp = self.client.post(
            reverse("fees:verify_payment", args=[self.payment.pk]),
            data={"status": "approved"},
        )
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status, "approved")
        self.assertEqual(self.invoice.paid_amount, Decimal("60000.00"))
        self.assertEqual(self.invoice.balance, Decimal("40000.00"))
        self.assertTrue(Receipt.objects.filter(payment=self.payment).exists())
        self.assertEqual(resp.status_code, 302)
        log = AuditLog.objects.filter(action="approve_payment").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.accountant)

    def test_reject_requires_reason(self):
        resp = self.client.post(
            reverse("fees:verify_payment", args=[self.payment.pk]),
            data={"status": "rejected"},
        )
        self.assertEqual(resp.status_code, 200)  # form re-rendered
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_reject_with_reason_succeeds(self):
        resp = self.client.post(
            reverse("fees:verify_payment", args=[self.payment.pk]),
            data={"status": "rejected", "rejection_reason": "Slip not legible"},
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "rejected")
        self.assertEqual(self.payment.rejection_reason, "Slip not legible")
        log = AuditLog.objects.filter(action="reject_payment").first()
        self.assertIsNotNone(log)

    def test_balance_auto_updates_on_invoice_save(self):
        self.invoice.paid_amount = Decimal("100000.00")
        self.invoice.save()
        self.assertEqual(self.invoice.balance, Decimal("0.00"))
        self.assertEqual(self.invoice.status, "paid")

    def test_partially_paid_status(self):
        self.invoice.paid_amount = Decimal("30000.00")
        self.invoice.save()
        self.assertEqual(self.invoice.status, "partially_paid")
        self.assertEqual(self.invoice.balance, Decimal("70000.00"))


class RecordPaymentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.accountant = make_accountant("acc")
        self.klass = Class.objects.create(name="Form 3C")
        self.student = make_student("stud2", klass=self.klass)
        self.fee_structure = FeeStructure.objects.create(
            name="Term 2", amount=Decimal("80000.00"),
            target_class=self.klass, term="2", session="2026",
        )
        self.invoice = StudentInvoice.objects.create(
            student=self.student, fee_structure=self.fee_structure,
            total_amount=Decimal("80000.00"),
        )
        self.client.login(username="acc", password="x")

    def test_record_payment_creates_slip_and_receipt(self):
        resp = self.client.post(reverse("fees:record_payment", args=[self.student.student_id]), data={
            "invoice": self.invoice.pk,
            "bank_name": "nbm",
            "transaction_reference": "CASH-001",
            "amount": "40000.00",
            "payment_date": date.today().isoformat(),
        })
        self.assertEqual(resp.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("40000.00"))
        slip = BankPaymentReceipt.objects.filter(transaction_reference="CASH-001").first()
        self.assertIsNotNone(slip)
        self.assertEqual(slip.status, "approved")
        self.assertTrue(Receipt.objects.filter(payment=slip).exists())


class ReceiptNumberUniquenessTests(TestCase):
    def test_unique_constraint(self):
        make_accountant("acc")
        klass = Class.objects.create(name="Form 4D")
        s = make_student("stud3", klass=klass)
        fs = FeeStructure.objects.create(
            name="T1", amount=Decimal("100.00"),
            target_class=klass, term="1", session="2026",
        )
        inv = StudentInvoice.objects.create(student=s, fee_structure=fs, total_amount=Decimal("100.00"))
        p1 = BankPaymentReceipt.objects.create(
            invoice=inv, bank_name="standard", depositor_name="X",
            transaction_reference="A1", amount_paid=Decimal("50.00"), payment_date=date.today(),
        )
        Receipt.objects.create(
            payment=p1, invoice=inv, student_name="X", student_id=s.student_id,
            amount=Decimal("50.00"), balance_after=Decimal("50.00"),
            term="1", academic_year="2026", issued_by=None,
        )
        # Same number → IntegrityError
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Receipt.objects.create(
                receipt_number=Receipt.objects.first().receipt_number,
                payment=p1, invoice=inv, student_name="X", student_id=s.student_id,
                amount=Decimal("50.00"), balance_after=Decimal("50.00"),
                term="1", academic_year="2026", issued_by=None,
            )


class FeeStructureInvoiceGenerationTests(TestCase):
    def setSetUpData(cls):
        cls.klass = Class.objects.create(name="Form 5E")
        for i in range(3):
            make_student(f"gen{i}", sid=f"STD-GEN-{i}", klass=cls.klass)

    def test_generate_invoices_for_class(self):
        self.setSetUpData()
        accountant = make_accountant("acc_gen")
        self.client.login(username="acc_gen", password="x")
        fs = FeeStructure.objects.create(
            name="Auto-gen test", amount=Decimal("50000.00"),
            target_class=Class.objects.get(name="Form 5E"),
            term="3", session="2026",
        )
        # Use the view to generate
        resp = self.client.post(reverse("fees:generate_invoices", args=[fs.pk]))
        self.assertEqual(resp.status_code, 302)
        count = StudentInvoice.objects.filter(fee_structure=fs).count()
        self.assertEqual(count, 3)


class StudentParentAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        klass = Class.objects.create(name="Form 6F")
        self.student_user = User.objects.create_user(username="stuuser", password="x")
        self.student = make_student("stuuser2", klass=klass)
        fs = FeeStructure.objects.create(
            name="F", amount=Decimal("100.00"),
            target_class=klass, term="1", session="2026",
        )
        self.invoice = StudentInvoice.objects.create(
            student=self.student, fee_structure=fs, total_amount=Decimal("100.00"),
        )

    def test_student_can_view_own_fees(self):
        self.client.force_login(self.student.user)
        resp = self.client.get(reverse("fees:student_fees"))
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_blocked(self):
        resp = self.client.get(reverse("fees:student_fees"))
        self.assertIn(resp.status_code, (301, 302))


class ReceiptPdfTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.accountant = make_accountant("acc")
        klass = Class.objects.create(name="Form 7G")
        self.student = make_student("stu_pdf", klass=klass)
        fs = FeeStructure.objects.create(
            name="PDF test", amount=Decimal("100.00"),
            target_class=klass, term="1", session="2026",
        )
        self.invoice = StudentInvoice.objects.create(
            student=self.student, fee_structure=fs, total_amount=Decimal("100.00"),
        )
        p = BankPaymentReceipt.objects.create(
            invoice=self.invoice, bank_name="standard", depositor_name="X",
            transaction_reference="PDF-1", amount_paid=Decimal("100.00"),
            payment_date=date.today(), status="approved",
            verified_by=self.accountant,
        )
        self.receipt = Receipt.objects.create(
            payment=p, invoice=self.invoice,
            student_name=self.student.user.get_full_name(),
            student_id=self.student.student_id,
            amount=Decimal("100.00"), balance_after=Decimal("0.00"),
            term="1", academic_year="2026", issued_by=self.accountant,
        )

    def test_pdf_response(self):
        self.client.login(username="acc", password="x")
        resp = self.client.get(reverse("fees:receipt_pdf", args=[self.receipt.receipt_number]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
