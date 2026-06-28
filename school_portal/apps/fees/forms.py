"""
Forms for the fees module.
"""
from datetime import date
from decimal import Decimal

from django import forms

from apps.parents.models import BankPaymentReceipt, FeeStructure, StudentInvoice
from apps.accounts.models import Student
from .models import Accountant


# ---------------------------------------------------------------------------
# Accountant search / verification
# ---------------------------------------------------------------------------

class StudentSearchForm(forms.Form):
    """Search the student directory by ID or name."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-input w-full rounded-xl border-surface-200 dark:border-surface-700 "
                     "bg-white dark:bg-surface-900 text-surface-900 dark:text-white "
                     "px-4 py-3 pl-11",
            "placeholder": "Search by Student ID or name...",
        }),
    )
    class_level = forms.ModelChoiceField(
        required=False,
        queryset=None,
        empty_label="All Classes",
        widget=forms.Select(attrs={
            "class": "form-input w-full rounded-xl border-surface-200 dark:border-surface-700 "
                     "bg-white dark:bg-surface-900 text-surface-900 dark:text-white px-4 py-3",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import Class
        self.fields["class_level"].queryset = Class.objects.all().order_by("name")


class RecordPaymentForm(forms.Form):
    """Form used by accountants to record and approve a payment directly."""

    invoice = forms.ModelChoiceField(
        queryset=StudentInvoice.objects.none(),
        required=True,
        empty_label="Select an unpaid invoice",
        widget=forms.Select(attrs={
            "class": "w-full px-4 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/60 "
                     "bg-white dark:bg-slate-800/40 text-sm focus:outline-none focus:ring-2 "
                     "focus:ring-scholarly-primary/40 focus:border-scholarly-primary",
        }),
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={
            "class": "w-full px-4 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/60 "
                     "bg-white dark:bg-slate-800/40 text-sm focus:outline-none focus:ring-2 "
                     "focus:ring-scholarly-primary/40 focus:border-scholarly-primary",
            "placeholder": "0.00",
            "step": "0.01",
            "min": "0.01",
        }),
    )
    bank_name = forms.ChoiceField(
        choices=BankPaymentReceipt.BANK_CHOICES,
        widget=forms.Select(attrs={
            "class": "w-full px-4 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/60 "
                     "bg-white dark:bg-slate-800/40 text-sm focus:outline-none focus:ring-2 "
                     "focus:ring-scholarly-primary/40 focus:border-scholarly-primary",
        }),
    )
    transaction_reference = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "w-full px-4 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/60 "
                     "bg-white dark:bg-slate-800/40 text-sm focus:outline-none focus:ring-2 "
                     "focus:ring-scholarly-primary/40 focus:border-scholarly-primary",
            "placeholder": "e.g. NBM-2026-001234",
        }),
    )
    payment_date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "w-full px-4 py-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/60 "
                     "bg-white dark:bg-slate-800/40 text-sm focus:outline-none focus:ring-2 "
                     "focus:ring-scholarly-primary/40 focus:border-scholarly-primary",
        }),
    )

    def __init__(self, *args, **kwargs):
        invoices = kwargs.pop("invoices", StudentInvoice.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["invoice"].queryset = invoices

    def clean_transaction_reference(self):
        return (self.cleaned_data.get("transaction_reference") or "").strip()

    def clean_payment_date(self):
        paid_on = self.cleaned_data["payment_date"]
        if paid_on > date.today():
            raise forms.ValidationError("Payment date cannot be in the future.")
        return paid_on


class VerifyPaymentForm(forms.ModelForm):
    """Form used by the accountant to approve/reject a pending bank slip."""

    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-input w-full rounded-xl border-surface-200 dark:border-surface-700 "
                     "bg-white dark:bg-surface-900 text-surface-900 dark:text-white px-4 py-3",
            "rows": 3,
            "placeholder": "Required only when rejecting — e.g. transaction not found on bank statement.",
        }),
    )

    class Meta:
        model = BankPaymentReceipt
        fields = ["status", "rejection_reason"]
        widgets = {
            "status": forms.Select(attrs={
                "class": "form-input w-full rounded-xl border-surface-200 dark:border-surface-700 "
                         "bg-white dark:bg-surface-900 text-surface-900 dark:text-white px-4 py-3",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            described_by = f"id_{field_name}_help"
            has_error = self.is_bound and field_name in self.errors
            if has_error:
                described_by = f"{described_by} id_{field_name}_error"
            field.widget.attrs["aria-describedby"] = described_by
            field.widget.attrs["aria-invalid"] = "true" if has_error else "false"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        reason = (cleaned.get("rejection_reason") or "").strip()
        if status == "rejected" and not reason:
            raise forms.ValidationError(
                "A rejection reason is required when rejecting a payment."
            )
        return cleaned


# ---------------------------------------------------------------------------
# Fee-structure management (admin)
# ---------------------------------------------------------------------------

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ["name", "amount", "target_class", "term", "session"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
            "amount": forms.NumberInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3", "min": "0"}),
            "target_class": forms.Select(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
            "term": forms.Select(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
            "session": forms.TextInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3", "placeholder": "e.g. 2026-2027"}),
        }


# ---------------------------------------------------------------------------
# Accountant profile
# ---------------------------------------------------------------------------

class AccountantForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
    )
    last_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3"}),
    )

    class Meta:
        model = Accountant
        fields = ["phone"]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-input w-full rounded-xl px-4 py-3", "placeholder": "+265 ..."}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["first_name"].initial = self.user.first_name
            self.fields["last_name"].initial = self.user.last_name
            self.fields["email"].initial = self.user.email

    def save(self, commit=True):
        accountant = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data["first_name"]
            self.user.last_name = self.cleaned_data["last_name"]
            self.user.email = self.cleaned_data["email"]
            if commit:
                self.user.save()
        if commit:
            accountant.save()
        return accountant
