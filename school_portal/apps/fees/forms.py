"""
Forms for the fees module.
"""
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
