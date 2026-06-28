import secrets

from django import forms
from django.contrib.auth.models import User
from .models import Parent, ParentStudentRelationship, BankPaymentReceipt
from apps.accounts.models import Student


def _generate_random_password(length: int = 14) -> str:
    """Return a cryptographically random password."""
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ParentProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)

    class Meta:
        model = Parent
        fields = ['phone_number', 'relationship']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if Parent.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This phone number is already in use.')
        return phone

    def save(self, commit=True):
        parent = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            if commit:
                self.user.save()
        if commit:
            parent.save()
        return parent


class ParentStudentLinkForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        label='Select Student',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    is_primary_contact = forms.BooleanField(
        required=False, initial=True,
        label='Primary contact for school communications'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.select_related(
            'user', 'current_class'
        ).all().order_by('user__first_name')


class AdminParentCreateForm(forms.ModelForm):
    """Form for admins to create parent accounts linked to students."""
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text='Leave blank to auto-generate a secure random password.',
    )

    class Meta:
        model = Parent
        fields = ['phone_number', 'relationship']

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if Parent.objects.filter(phone_number=phone).exclude(
            pk=self.instance.pk
        ).exists():
            raise forms.ValidationError('A parent with this phone number already exists.')
        return phone

    def save(self, commit=True, student=None):
        phone = self.cleaned_data['phone_number']
        password = self.cleaned_data.get('password') or _generate_random_password()

        # Username is decoupled from the phone number (which is widely known)
        # to prevent credential enumeration. Parents still log in via the
        # custom parent login form, which accepts the phone number.
        username = f"par_{secrets.token_urlsafe(9)}"
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data.get('email', ''),
        )

        parent = super().save(commit=False)
        parent.user = user
        if commit:
            parent.save()
            if student:
                ParentStudentRelationship.objects.create(
                    parent=parent,
                    student=student,
                    is_primary_contact=True,
                )
        # Expose the generated password for the view to surface once.
        parent._initial_password = password
        return parent


class BankPaymentReceiptForm(forms.ModelForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(), required=False,
        label='Student',
        widget=forms.Select(attrs={'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3'}),
    )

    class Meta:
        model = BankPaymentReceipt
        fields = [
            'student', 'bank_name', 'depositor_name', 'transaction_reference',
            'amount_paid', 'payment_date', 'deposit_slip_image'
        ]

    def __init__(self, *args, **kwargs):
        parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)
        if parent:
            self.fields['student'].queryset = Student.objects.filter(
                parent_relationships__parent=parent
            ).select_related('user', 'current_class').order_by('user__first_name')
            self.fields['student'].required = True
        else:
            del self.fields['student']
        widget_attrs = {
            'student': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
            },
            'bank_name': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
            },
            'depositor_name': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
                'placeholder': 'Enter full name',
                'autocomplete': 'name',
            },
            'transaction_reference': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
                'placeholder': 'Reference number from bank slip',
                'autocomplete': 'off',
            },
            'amount_paid': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
                'placeholder': 'Amount paid in MWK',
                'min': '0',
                'step': '0.01',
                'inputmode': 'decimal',
            },
            'payment_date': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
                'type': 'date',
            },
            'deposit_slip_image': {
                'class': 'form-input w-full rounded-xl border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800 text-surface-900 dark:text-white px-4 py-3',
                'accept': '.jpg,.jpeg,.png,image/jpeg,image/png',
            },
        }

        for field_name, attrs in widget_attrs.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update(attrs)

        for field_name, field in self.fields.items():
            described_by = f'id_{field_name}_help'
            has_error = self.is_bound and field_name in self.errors
            if has_error:
                described_by = f'{described_by} id_{field_name}_error'
            field.widget.attrs['aria-describedby'] = described_by
            field.widget.attrs['aria-invalid'] = 'true' if has_error else 'false'

    def clean_deposit_slip_image(self):
        image = self.cleaned_data.get('deposit_slip_image')
        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image is too large (max 5MB). Please compress and try again.')
            if image.content_type not in ('image/jpeg', 'image/png'):
                raise forms.ValidationError('Only JPG and PNG images are accepted.')
            # Verify the file is actually an image by inspecting magic bytes.
            # The Content-Type header is attacker-controlled, so we cannot
            # trust it alone.
            try:
                header = image.read(12)
                image.seek(0)
            except Exception:
                header = b''
            is_jpeg = header.startswith(b'\xff\xd8\xff')
            is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
            if not (is_jpeg or is_png):
                raise forms.ValidationError(
                    'The uploaded file is not a valid JPG or PNG image.'
                )
        return image

