import re
import logging
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import Student

logger = logging.getLogger(__name__)

RELATIONSHIP_CHOICES = [
    ('father', 'Father'),
    ('mother', 'Mother'),
    ('guardian', 'Guardian'),
    ('grandparent', 'Grandparent'),
    ('aunt', 'Aunt'),
    ('uncle', 'Uncle'),
    ('other', 'Other'),
]


def validate_phone_number(value):
    pattern = r'^\+?[\d\s\-\(\)]{7,20}$'
    if not re.match(pattern, value):
        raise ValidationError(
            'Enter a valid phone number (7-20 digits, optionally with +, -, spaces, or parentheses).'
        )


def generate_parent_id():
    last_parent = Parent.objects.select_for_update().order_by('id').last()
    if last_parent and last_parent.parent_id:
        try:
            last_num = int(last_parent.parent_id.split('-')[1])
            new_num = last_num + 1
        except (IndexError, ValueError):
            new_num = 1
    else:
        new_num = 1
    return f'PAR-{new_num:04d}'


class Parent(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='parent'
    )
    parent_id = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True
    )
    phone_number = models.CharField(
        max_length=20, validators=[validate_phone_number],
        unique=True, help_text='Primary phone number for login (e.g., 0991234567)'
    )
    relationship = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES, default='guardian'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['parent_id']
        verbose_name = 'Parent/Guardian'
        verbose_name_plural = 'Parents/Guardians'

    def save(self, *args, **kwargs):
        if not self.parent_id:
            with transaction.atomic():
                self.parent_id = generate_parent_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.parent_id})'

    def get_relationship_display_name(self):
        return dict(RELATIONSHIP_CHOICES).get(self.relationship, self.relationship)

    @property
    def children_count(self):
        return self.children.count()

    @property
    def children(self):
        return Student.objects.filter(
            parent_relationships__parent=self
        ).select_related('user', 'current_class')


class ParentStudentRelationship(models.Model):
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE,
        related_name='student_relationships'
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='parent_relationships'
    )
    is_primary_contact = models.BooleanField(
        default=False,
        help_text='Primary contact for school communications'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['parent', 'student']
        ordering = ['parent', 'student']
        verbose_name = 'Parent-Student Relationship'
        verbose_name_plural = 'Parent-Student Relationships'

    def __str__(self):
        return f'{self.parent} → {self.student}'


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, db_index=True
    )
    term = models.CharField(max_length=3, choices=[
        ('1st', 'First Term'), ('2nd', 'Second Term'), ('3rd', 'Third Term'),
    ], db_index=True)
    session = models.CharField(max_length=9, db_index=True)
    remarks = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_attendance'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'date', 'term', 'session']
        ordering = ['-date']
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f'{self.student.student_id} - {self.date} - {self.get_status_display()}'

    @classmethod
    def get_student_summary(cls, student, term=None, session=None):
        filters = {'student': student}
        if term:
            filters['term'] = term
        if session:
            filters['session'] = session

        records = cls.objects.filter(**filters)
        total = records.count()
        present = records.filter(status='present').count()
        absent = records.filter(status='absent').count()
        late = records.filter(status='late').count()
        excused = records.filter(status='excused').count()

        percentage = round((present / total * 100), 1) if total > 0 else 0

        return {
            'total': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'percentage': percentage,
        }


class ParentNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('in_app', 'In-App'),
        ('push', 'Push Notification'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]

    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=10, choices=NOTIFICATION_TYPES, default='in_app'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    related_student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Parent Notification'
        verbose_name_plural = 'Parent Notifications'

    def __str__(self):
        return f'{self.parent.parent_id} - {self.title}'

    def mark_as_sent(self):
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_as_read(self):
        self.status = 'read'
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'read_at'])


class ParentAnnouncementRead(models.Model):
    parent = models.ForeignKey(
        Parent, on_delete=models.CASCADE, related_name='read_announcements'
    )
    announcement = models.ForeignKey(
        'announcements.Announcement', on_delete=models.CASCADE,
        related_name='read_by_parents'
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['parent', 'announcement']
        verbose_name = 'Parent Announcement Read Status'
        verbose_name_plural = 'Parent Announcement Read Statuses'

    def __str__(self):
        return f'{self.parent.parent_id} read {self.announcement.title}'


class FeeStructure(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Term 1 Tuition Fee")
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in MWK")
    target_class = models.ForeignKey(
        'accounts.Class', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fee_structures',
        help_text="Leave blank if this fee applies to all classes."
    )
    term = models.CharField(max_length=3, choices=[('1st', 'First Term'), ('2nd', 'Second Term'), ('3rd', 'Third Term')])
    session = models.CharField(max_length=9, help_text="e.g., 2026-2027")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session', 'term', 'name']

    def __str__(self):
        class_str = f" - {self.target_class}" if self.target_class else " - All Classes"
        return f"{self.name} ({self.session} {self.term}){class_str} - MWK {self.amount:,.2f}"


class StudentInvoice(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
    ]
    student = models.ForeignKey(
        'accounts.Student', on_delete=models.CASCADE, related_name='invoices'
    )
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name='invoices'
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='unpaid', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'fee_structure']
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Set total amount from structure if not manually overwritten
        if not self.total_amount and self.fee_structure:
            self.total_amount = self.fee_structure.amount
        
        # Calculate balance and status
        paid = Decimal(str(self.paid_amount or 0))
        self.balance = Decimal(str(self.total_amount)) - paid
        if paid <= 0:
            self.status = 'unpaid'
        elif self.balance <= 0:
            self.status = 'paid'
            self.balance = Decimal("0.00") # Avoid negative balance
        else:
            self.status = 'partially_paid'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.fee_structure.name} - Bal: MWK {self.balance:,.2f}"


class BankPaymentReceipt(models.Model):
    BANK_CHOICES = [
        ('nbm', 'National Bank of Malawi'),
        ('standard', 'Standard Bank'),
        ('nbs', 'NBS Bank'),
        ('fdh', 'FDH Bank'),
        ('fcb', 'First Capital Bank'),
        ('ecobank', 'EcoBank'),
        ('mybucks', 'MyBucks'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved / Paid'),
        ('rejected', 'Rejected'),
    ]
    invoice = models.ForeignKey(
        StudentInvoice, on_delete=models.CASCADE, related_name='receipts',
        null=True, blank=True,
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='payment_receipts',
        null=True, blank=True,
    )
    bank_name = models.CharField(max_length=20, choices=BANK_CHOICES)
    depositor_name = models.CharField(max_length=150, help_text="Name of the person who made the deposit")
    transaction_reference = models.CharField(max_length=100, unique=True, help_text="Unique reference number stamped on the bank slip")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount deposited in MWK")
    payment_date = models.DateField(help_text="Date of deposit at the bank")
    deposit_slip_image = models.ImageField(upload_to='deposit_slips/', help_text="Clear photo or scan of the stamped deposit slip")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_receipts'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection, visible to parents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def resolved_student(self):
        return self.student or (self.invoice.student if self.invoice else None)

    def __str__(self):
        student = self.resolved_student
        if student:
            return f"Receipt {self.transaction_reference} for {student.user.get_full_name()} - MWK {self.amount_paid:,.2f}"
        return f"Receipt {self.transaction_reference} - MWK {self.amount_paid:,.2f}"

