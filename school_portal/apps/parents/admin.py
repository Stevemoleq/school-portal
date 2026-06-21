from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from .models import (
    Parent, ParentStudentRelationship, Attendance, ParentNotification, 
    ParentAnnouncementRead, FeeStructure, StudentInvoice, BankPaymentReceipt
)
from apps.accounts.models import Student
from apps.accounts.admin import StudentResource
import secrets
import string


def _generate_random_password(length=12):
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


class ParentStudentRelationshipInline(admin.TabularInline):
    model = ParentStudentRelationship
    extra = 1
    autocomplete_fields = ['student']
    verbose_name = 'Linked Student'
    verbose_name_plural = 'Linked Students'


class StudentParentInline(admin.TabularInline):
    model = ParentStudentRelationship
    extra = 1
    autocomplete_fields = ['parent']
    verbose_name = 'Parent/Guardian'
    verbose_name_plural = 'Parents/Guardians'


class ParentResource(resources.ModelResource):
    first_name = fields.Field(attribute='user__first_name', column_name='first_name')
    last_name = fields.Field(attribute='user__last_name', column_name='last_name')
    email = fields.Field(attribute='user__email', column_name='email')

    class Meta:
        model = Parent
        import_id_fields = ('parent_id',)
        fields = ('parent_id', 'first_name', 'last_name', 'email', 'phone_number', 'relationship')
        skip_unchanged = True

    def before_import_row(self, row, **kwargs):
        first_name = row.get('first_name', '')
        last_name = row.get('last_name', '')
        email = row.get('email', '')
        phone = row.get('phone_number', '')

        username = f'parent_{phone}'

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            }
        )
        if created:
            user.set_password(_generate_random_password())
            user.save()
        row['user'] = user.id


class ParentAdminForm(forms.ModelForm):
    """Custom form for Parent admin that handles User creation automatically."""
    first_name = forms.CharField(max_length=150, required=True, help_text="Parent's first name")
    last_name = forms.CharField(max_length=150, required=True, help_text="Parent's last name")
    email = forms.EmailField(required=False, help_text="Parent's email address (optional)")
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text="Leave blank to auto-generate a secure random password.",
    )

    class Meta:
        model = Parent
        fields = [
            'first_name', 'last_name', 'email', 'password',
            'phone_number', 'relationship',
        ]

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if Parent.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This phone number is already in use.')
        return phone

    def save(self, commit=True):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        email = self.cleaned_data.get('email', '')
        phone = self.cleaned_data['phone_number']
        password = self.cleaned_data.get('password') or _generate_random_password()

        # If this is a new parent (no user yet), create the User
        if not self.instance.pk:
            username = f'parent_{phone}'
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            parent = super().save(commit=False)
            parent.user = user
            if commit:
                parent.save()
            return parent

        # Updating existing parent
        parent = super().save(commit=False)
        if parent.user:
            parent.user.first_name = first_name
            parent.user.last_name = last_name
            parent.user.email = email
            if commit:
                parent.user.save()
                parent.save()
        return parent


@admin.register(Parent)
class ParentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    form = ParentAdminForm
    resource_class = ParentResource
    inlines = [ParentStudentRelationshipInline]
    list_display = ('parent_id', 'get_full_name', 'phone_number', 'relationship', 'children_count_display', 'created_at')
    list_display_links = ('parent_id', 'get_full_name')
    search_fields = ('parent_id', 'phone_number', 'user__first_name', 'user__last_name')
    list_filter = ('relationship', 'created_at')
    readonly_fields = ('parent_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    add_fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'password'),
            'description': 'A User account will be auto-created. Username = parent_{phone}. A secure random password is generated if left blank.',
        }),
        ('Contact Information', {
            'fields': ('phone_number',),
        }),
        ('Relationship', {
            'fields': ('relationship',),
        }),
    )

    change_fieldsets = (
        ('Parent ID (Auto-generated)', {
            'fields': ('parent_id',),
        }),
        ('Personal Information', {
            'fields': ('phone_number',),
        }),
        ('Relationship', {
            'fields': ('relationship',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.change_fieldsets

    def get_readonly_fields(self, request, obj=None):
        base = ['parent_id', 'created_at', 'updated_at']
        if obj:
            base.append('phone_number')
        return base

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.parent_id
    get_full_name.short_description = 'Name'
    get_full_name.admin_order_field = 'user__first_name'

    def children_count_display(self, obj):
        count = obj.children_count
        url = reverse('admin:parents_parentstudentrelationship_changelist') + f'?parent__id__exact={obj.pk}'
        return format_html('<a href="{}">{} child{}</a>', url, count, 'ren' if count != 1 else '')
    children_count_display.short_description = 'Children'


@admin.register(ParentStudentRelationship)
class ParentStudentRelationshipAdmin(admin.ModelAdmin):
    list_display = ('parent', 'student', 'is_primary_contact', 'created_at')
    list_filter = ('is_primary_contact', 'created_at')
    search_fields = ('parent__parent_id', 'parent__user__first_name', 'parent__user__last_name', 'student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ['parent', 'student']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'term', 'session', 'recorded_by')
    list_filter = ('status', 'term', 'session', 'date')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ['student', 'recorded_by']
    date_hierarchy = 'date'


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ('parent', 'title', 'notification_type', 'status', 'sent_at', 'created_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('parent__parent_id', 'title', 'message')
    autocomplete_fields = ['parent', 'related_student']
    readonly_fields = ('created_at', 'sent_at', 'read_at')

    actions = ['mark_as_sent_selected', 'mark_as_read_selected']

    def mark_as_sent_selected(self, request, queryset):
        for notification in queryset:
            notification.mark_as_sent()
        self.message_user(request, f'{queryset.count()} notification(s) marked as sent.')
    mark_as_sent_selected.short_description = 'Mark selected notifications as sent'

    def mark_as_read_selected(self, request, queryset):
        for notification in queryset:
            notification.mark_as_read()
        self.message_user(request, f'{queryset.count()} notification(s) marked as read.')
    mark_as_read_selected.short_description = 'Mark selected notifications as read'


@admin.register(ParentAnnouncementRead)
class ParentAnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ('parent', 'announcement', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('parent__parent_id', 'announcement__title')
    autocomplete_fields = ['parent', 'announcement']
    readonly_fields = ('read_at',)


# Inject student parent inline into existing StudentAdmin
from apps.accounts.admin import StudentAdmin
existing_inlines = list(getattr(StudentAdmin, 'inlines', []))
StudentAdmin.inlines = existing_inlines + [StudentParentInline]


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'target_class', 'term', 'session', 'created_at')
    list_filter = ('term', 'session', 'target_class')
    search_fields = ('name',)
    ordering = ('-session', 'term', 'name')


@admin.register(StudentInvoice)
class StudentInvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'total_amount', 'paid_amount', 'balance', 'status')
    list_filter = ('status', 'fee_structure__term', 'fee_structure__session')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    readonly_fields = ('balance', 'status')
    ordering = ('-created_at',)


@admin.register(BankPaymentReceipt)
class BankPaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('transaction_reference', 'get_student_name', 'bank_name', 'amount_paid', 'payment_date', 'status', 'verified_by')
    list_filter = ('status', 'bank_name', 'payment_date')
    search_fields = ('transaction_reference', 'depositor_name', 'invoice__student__student_id', 'invoice__student__user__first_name', 'student__student_id', 'student__user__first_name')
    readonly_fields = ('verified_by', 'verified_at', 'get_slip_image_preview')
    fields = ('student', 'invoice', 'bank_name', 'depositor_name', 'transaction_reference', 'amount_paid', 'payment_date', 'deposit_slip_image', 'get_slip_image_preview', 'status', 'rejection_reason', 'verified_by', 'verified_at')
    actions = ['approve_selected_receipts', 'reject_selected_receipts']

    def get_student_name(self, obj):
        student = obj.student or (obj.invoice.student if obj.invoice else None)
        if student:
            return student.user.get_full_name()
        return "—"
    get_student_name.short_description = 'Student'

    def get_slip_image_preview(self, obj):
        if obj.deposit_slip_image:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 300px; border-radius: 8px; border: 1px solid #ddd;" /></a>', obj.deposit_slip_image.url, obj.deposit_slip_image.url)
        return "No image uploaded"
    get_slip_image_preview.short_description = 'Slip Preview'

    def _student_id_from_receipt(self, receipt):
        student = receipt.student or (receipt.invoice.student if receipt.invoice else None)
        return student.student_id if student else "N/A"

    def approve_selected_receipts(self, request, queryset):
        from django.utils import timezone
        count = 0
        for receipt in queryset.filter(status='pending'):
            receipt.status = 'approved'
            receipt.verified_by = request.user
            receipt.verified_at = timezone.now()
            receipt.save()
            
            # Update invoice balance (skip if no invoice linked)
            invoice = receipt.invoice
            if invoice is not None:
                invoice.paid_amount += receipt.amount_paid
                invoice.save()
            count += 1
            
            # Audit log
            from apps.core.logging_utils import log_user_action
            log_user_action(
                f"Approved payment slip reference {receipt.transaction_reference} for {self._student_id_from_receipt(receipt)}",
                user=request.user,
                details={'amount': float(receipt.amount_paid), 'student_id': self._student_id_from_receipt(receipt)}
            )
        self.message_user(request, f'{count} payment receipt(s) approved and student accounts credited.')
    approve_selected_receipts.short_description = 'Approve selected pending receipts'

    def reject_selected_receipts(self, request, queryset):
        from django.utils import timezone
        count = 0
        for receipt in queryset.filter(status='pending'):
            receipt.status = 'rejected'
            receipt.verified_by = request.user
            receipt.verified_at = timezone.now()
            if not receipt.rejection_reason:
                receipt.rejection_reason = "Transaction reference could not be verified on school bank statement."
            receipt.save()
            count += 1
            
            # Audit log
            from apps.core.logging_utils import log_user_action
            log_user_action(
                f"Rejected payment slip reference {receipt.transaction_reference} for {self._student_id_from_receipt(receipt)}",
                user=request.user,
                details={'student_id': self._student_id_from_receipt(receipt)}
            )
        self.message_user(request, f'{count} payment receipt(s) marked as rejected.')
    reject_selected_receipts.short_description = 'Reject selected pending receipts'

