"""
Tuition Fees Management Models
===============================

This module adds the supporting models for the fees system:

* ``Accountant``  - profile model for the new Accountant role
* ``Receipt``     - auto-generated official receipt issued for each approved payment
* ``AuditLog``    - immutable audit trail for all financial actions

The actual fee/invoice/payment models live in ``apps.parents.models`` to keep
backward compatibility with the existing data model that was already in place.
"""
import logging
import secrets

from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.parents.models import BankPaymentReceipt, StudentInvoice

logger = logging.getLogger(__name__)


def _generate_receipt_number():
    """Generate a unique, human-readable receipt number.

    Format: ``RCP-YYYYMMDD-XXXXXX`` where XXXXXX is a 6-char random
    alphanumeric token.  The token is regenerated on collision.
    """
    import datetime as _dt
    date_part = _dt.date.today().strftime("%Y%m%d")
    for _ in range(10):
        token = secrets.token_hex(3).upper()
        candidate = f"RCP-{date_part}-{token}"
        if not Receipt.objects.filter(receipt_number=candidate).exists():
            return candidate
    # Last-resort fallback - extremely unlikely to reach here
    return f"RCP-{date_part}-{secrets.token_hex(6).upper()}"


def _generate_accountant_id():
    """Generate sequential accountant IDs like ACC-0001."""
    last = Accountant.objects.order_by("-id").first()
    if last and last.accountant_id:
        try:
            n = int(last.accountant_id.split("-")[1]) + 1
        except (IndexError, ValueError):
            n = 1
    else:
        n = 1
    return f"ACC-{n:04d}"


class Accountant(models.Model):
    """Profile model for users with the Accountant role.

    Mirrors the pattern used by ``Teacher`` and ``Parent`` so that
    ``request.user.accountant`` reliably works across the system.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="accountant"
    )
    accountant_id = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True
    )
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["accountant_id"]
        verbose_name = "Accountant"
        verbose_name_plural = "Accountants"

    def save(self, *args, **kwargs):
        if not self.accountant_id:
            with transaction.atomic():
                self.accountant_id = _generate_accountant_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.accountant_id})"


class Receipt(models.Model):
    """Official receipt issued when a bank payment is approved.

    A receipt is **always** linked to a single approved
    ``BankPaymentReceipt``.  It is generated automatically by the
    accountant's verification workflow and is considered the school's
    legal record of the payment.
    """

    receipt_number = models.CharField(
        max_length=30, unique=True, editable=False, db_index=True
    )
    payment = models.OneToOneField(
        BankPaymentReceipt,
        on_delete=models.CASCADE,
        related_name="receipt",
        help_text="The bank payment this receipt is issued for.",
    )
    invoice = models.ForeignKey(
        StudentInvoice,
        on_delete=models.CASCADE,
        related_name="official_receipts",
        null=True, blank=True,
    )
    student_name = models.CharField(max_length=200)
    student_id = models.CharField(max_length=25, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Outstanding balance after this payment was applied.",
    )
    TERM_CHOICES = [
        ('1st', 'First Term'),
        ('2nd', 'Second Term'),
        ('3rd', 'Third Term'),
    ]
    term = models.CharField(max_length=3, choices=TERM_CHOICES, db_index=True)
    academic_year = models.CharField(max_length=9)
    date_issued = models.DateTimeField(default=timezone.now, db_index=True)
    issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="receipts_issued",
    )

    class Meta:
        ordering = ["-date_issued"]
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = _generate_receipt_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} — {self.student_id} — MWK {self.amount:,.2f}"


class AuditLog(models.Model):
    """Append-only audit trail for all financial actions.

    Records who did what, when, and (when applicable) the previous and new
    values.  ``AuditLog`` rows are never updated or deleted by application
    code.
    """

    ACTION_CHOICES = [
        ("approve_payment", "Approved Payment"),
        ("reject_payment", "Rejected Payment"),
        ("record_payment", "Recorded Payment"),
        ("create_fee_structure", "Created Fee Structure"),
        ("update_fee_structure", "Updated Fee Structure"),
        ("create_invoice", "Created Invoice"),
        ("submit_bank_slip", "Bank Slip Submitted"),
        ("issue_receipt", "Receipt Issued"),
        ("download_receipt", "Receipt Downloaded"),
        ("view_report", "Viewed Report"),
    ]

    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fees_audit_logs",
    )
    actor_role = models.CharField(max_length=30, blank=True)
    target_model = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=60, blank=True, db_index=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.action} by {self.actor or 'system'}"


class FeeConfiguration(models.Model):
    """Singleton-style configuration for school-wide fee settings.

    Stores the school name and the next sequence used in receipt
    numbers, plus any other global fee-related options.
    """

    school_name = models.CharField(max_length=200, default="Nazarene Secondary School")
    school_motto = models.CharField(max_length=200, blank=True, default="Excellence & Integrity")
    school_phone = models.CharField(max_length=30, blank=True)
    school_email = models.EmailField(blank=True)
    school_address = models.CharField(max_length=255, blank=True)
    receipt_prefix = models.CharField(max_length=10, default="RCP")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fee Configuration"
        verbose_name_plural = "Fee Configuration"

    def __str__(self):
        return f"Fee Configuration — {self.school_name}"

    def save(self, *args, **kwargs):
        # Enforce singleton behaviour — only one row allowed.
        if not self.pk and FeeConfiguration.objects.exists():
            existing = FeeConfiguration.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Return the single configuration row, creating it if missing."""
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()
