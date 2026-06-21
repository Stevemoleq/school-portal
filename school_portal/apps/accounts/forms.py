import secrets
import string

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Student, Class, Subject, Teacher


def _generate_random_password(length: int = 14) -> str:
    """Return a cryptographically random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


_TEXT_INPUT = {'class': 'form-input'}
_SELECT = {'class': 'form-input'}


class TeacherCreateForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={**_TEXT_INPUT, 'placeholder': 'name@example.com'}),
    )
    phone = forms.CharField(
        max_length=15, required=False,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., +254 712 345678'}),
    )
    date_hired = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_TEXT_INPUT, 'type': 'date'}),
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.select_related('assigned_class').order_by(
            'assigned_class__name', 'name'
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Tick the subjects this teacher will teach.",
    )
    auto_password = forms.BooleanField(
        required=False, initial=True,
        help_text="Generate a random initial password (teacher should change it on first login).",
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={**_TEXT_INPUT, 'placeholder': 'Set a custom password'}),
        help_text="Ignored if 'Auto-generate random password' is checked.",
    )

    class Meta:
        model = Teacher
        fields = [
            'employee_id', 'first_name', 'last_name', 'email',
            'phone', 'date_hired', 'subjects',
        ]
        widgets = {
            'employee_id': forms.TextInput(attrs={
                **_TEXT_INPUT, 'placeholder': 'e.g., TCH-001',
            }),
        }

    def clean_employee_id(self):
        emp_id = self.cleaned_data['employee_id'].strip()
        if Teacher.objects.filter(employee_id__iexact=emp_id).exists():
            raise ValidationError("A teacher with this Employee ID already exists.")
        if User.objects.filter(username__iexact=emp_id).exists():
            raise ValidationError("A user with this username already exists.")
        return emp_id

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('auto_password') and not cleaned.get('password'):
            self.add_error('password', "Provide a password or check 'Use Employee ID'.")
        return cleaned

    def save(self, commit=True):
        teacher = super().save(commit=False)
        emp_id = self.cleaned_data['employee_id'].strip()
        auto = self.cleaned_data.get('auto_password')
        password = (
            self.cleaned_data.get('password')
            if not auto
            else _generate_random_password()
        )

        # Username is decoupled from employee_id to prevent enumeration.
        username = f"tch_{secrets.token_urlsafe(9)}"
        user = User.objects.create_user(
            username=username,
            email=self.cleaned_data['email'],
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )
        teacher.user = user

        if commit:
            teacher.save()
            self.save_m2m()
        # Expose the generated password on the instance for the view to
        # surface to the operator exactly once.
        teacher._initial_password = password
        return teacher


class TeacherEditForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={**_TEXT_INPUT, 'placeholder': 'name@example.com'}),
    )
    phone = forms.CharField(
        max_length=15, required=False,
        widget=forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., +254 712 345678'}),
    )
    date_hired = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_TEXT_INPUT, 'type': 'date'}),
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.select_related('assigned_class').order_by(
            'assigned_class__name', 'name'
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Tick the subjects this teacher will teach.",
    )

    class Meta:
        model = Teacher
        fields = [
            'employee_id', 'first_name', 'last_name', 'email',
            'phone', 'date_hired', 'subjects',
        ]
        widgets = {
            'employee_id': forms.TextInput(attrs={
                **_TEXT_INPUT, 'placeholder': 'e.g., TCH-001', 'readonly': True,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def clean_employee_id(self):
        emp_id = self.cleaned_data['employee_id'].strip()
        if self.instance and self.instance.employee_id == emp_id:
            return emp_id
        if Teacher.objects.filter(employee_id__iexact=emp_id).exists():
            raise ValidationError("A teacher with this Employee ID already exists.")
        return emp_id

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if self.instance and self.instance.user.email == email:
            return email
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        teacher = super().save(commit=False)
        user = teacher.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            teacher.save()
            self.save_m2m()
        return teacher


class ClassCreateForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'section']
        widgets = {
            'name': forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., Form 1'}),
            'section': forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., A, B, Blue'}),
        }

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name', '').strip()
        section = cleaned.get('section', '').strip()
        if name:
            qs = Class.objects.filter(name__iexact=name)
            if section:
                qs = qs.filter(section__iexact=section)
            else:
                qs = qs.filter(section='')
            if qs.exists():
                raise ValidationError(
                    f"A class named '{name} {section}' already exists."
                )
        return cleaned


class SubjectCreateForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'assigned_class']
        widgets = {
            'name': forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., Mathematics'}),
            'code': forms.TextInput(attrs={**_TEXT_INPUT, 'placeholder': 'e.g., MATH'}),
            'assigned_class': forms.Select(attrs=_SELECT),
        }

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if Subject.objects.filter(code__iexact=code).exists():
            raise ValidationError("A subject with this code already exists.")
        return code
