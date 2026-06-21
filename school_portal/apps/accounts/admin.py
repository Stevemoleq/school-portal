import secrets
import string

from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, DateWidget
from .models import Class, Subject, Student, Teacher, StudentSubject
from .student_id import generate_student_id


def _generate_random_password(length=12):
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    # Ensure at least one of each category
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'get_student_count',
                    'get_subject_count', 'created_at')
    search_fields = ('name', 'section')
    list_filter = ('section',)
    ordering = ('name', 'section')

    def get_student_count(self, obj):
        return obj.students.count()
    get_student_count.short_description = 'Students'

    def get_subject_count(self, obj):
        return obj.subjects.count()
    get_subject_count.short_description = 'Subjects'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'assigned_class', 'category',
                    'is_compulsory', 'get_teacher_count', 'get_student_count',
                    'created_at')
    list_filter = ('is_compulsory', 'category', 'assigned_class')
    search_fields = ('name', 'code')
    ordering = ('is_compulsory', 'name')
    list_select_related = ('assigned_class',)
    list_editable = ('is_compulsory', 'category')
    fieldsets = (
        (None, {'fields': ('name', 'code', 'assigned_class')}),
        ('Classification', {
            'fields': ('category', 'is_compulsory'),
            'description': 'Compulsory subjects are automatically assigned to every student.',
        }),
    )

    def get_teacher_count(self, obj):
        count = obj.teachers.count()
        return count if count else '—'
    get_teacher_count.short_description = 'Teachers'

    def get_student_count(self, obj):
        return obj.student_subjects.count()
    get_student_count.short_description = 'Enrolled'


@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'is_elective', 'created_at')
    list_filter = ('subject__is_compulsory', 'subject__category', 'is_elective')
    search_fields = (
        'student__student_id', 'student__user__first_name', 'student__user__last_name',
        'subject__name', 'subject__code',
    )
    autocomplete_fields = ('student', 'subject')
    list_select_related = ('student__user', 'subject')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


class StudentResource(resources.ModelResource):
    first_name = fields.Field(attribute='first_name', column_name='first_name')
    last_name = fields.Field(attribute='last_name', column_name='last_name')
    email = fields.Field(attribute='email', column_name='email')
    admission_form = fields.Field(attribute='admission_form', column_name='admission_form')
    admission_year = fields.Field(attribute='admission_year', column_name='admission_year')
    current_class = fields.Field(
        column_name='current_class',
        attribute='current_class',
        widget=ForeignKeyWidget(Class, 'name')
    )
    date_of_birth = fields.Field(
        attribute='date_of_birth', column_name='date_of_birth', widget=DateWidget()
    )
    address = fields.Field(attribute='address', column_name='address')

    class Meta:
        model = Student
        import_id_fields = ('student_id',)
        fields = (
            'student_id', 'first_name', 'last_name', 'email',
            'admission_form', 'admission_year', 'current_class',
            'date_of_birth', 'address',
        )
        skip_unchanged = True
        export_order = (
            'student_id', 'first_name', 'last_name', 'email',
            'admission_form', 'admission_year', 'current_class',
            'date_of_birth', 'address',
        )

    def before_import_row(self, row, **kwargs):
        from django.utils import timezone
        from .student_id import generate_student_id
        existing_student_id = row.get('student_id', '').strip()
        if existing_student_id:
            student_id = existing_student_id
            existing_student = Student.objects.filter(student_id=student_id).first()
            if existing_student:
                row['user'] = existing_student.user_id
                return
        else:
            admission_year = row.get('admission_year') or timezone.now().year
            admission_form = row.get('admission_form', 'Form 1')
            student_id = generate_student_id(
                admission_year=int(admission_year),
                admission_form=admission_form,
            )
            row['student_id'] = student_id
        first_name = row.get('first_name', '')
        last_name = row.get('last_name', '')
        email = row.get('email', '')
        password = row.get('password', '').strip() or _generate_random_password()
        username = f"stu_{secrets.token_urlsafe(9)}"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            }
        )
        if created:
            user.set_password(password)
            user.save()
        row['user'] = user.id

    def after_import_row(self, row, row_result, **kwargs):
        if row_result.import_type in ('new', 'update'):
            student = row_result.instance
            if row_result.import_type == 'new':
                student.must_change_password = True
                student.save(update_fields=['must_change_password'])
            student.assign_compulsory_subjects()

    def dehydrate_first_name(self, student):
        return student.user.first_name

    def dehydrate_last_name(self, student):
        return student.user.last_name

    def dehydrate_email(self, student):
        return student.user.email


class TeacherResource(resources.ModelResource):
    first_name = fields.Field(attribute='first_name', column_name='first_name')
    last_name = fields.Field(attribute='last_name', column_name='last_name')
    email = fields.Field(attribute='email', column_name='email')
    employee_id = fields.Field(attribute='employee_id', column_name='employee_id')
    phone = fields.Field(attribute='phone', column_name='phone')
    date_hired = fields.Field(
        attribute='date_hired', column_name='date_hired', widget=DateWidget()
    )
    subjects = fields.Field(attribute='subjects', column_name='subjects')

    class Meta:
        model = Teacher
        import_id_fields = ('employee_id',)
        fields = (
            'employee_id', 'first_name', 'last_name', 'email',
            'phone', 'date_hired', 'subjects',
        )
        skip_unchanged = True
        export_order = (
            'employee_id', 'first_name', 'last_name', 'email',
            'phone', 'date_hired', 'subjects',
        )

    def before_import_row(self, row, **kwargs):
        username = row['employee_id']
        first_name = row.get('first_name', '')
        last_name = row.get('last_name', '')
        email = row.get('email', '')
        password = row.get('password', '').strip() or _generate_random_password()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            }
        )
        if created:
            user.set_password(password)
            user.save()
        teacher, teacher_created = Teacher.objects.get_or_create(
            employee_id=row['employee_id'],
            defaults={
                'user': user,
                'phone': row.get('phone', ''),
                'date_hired': row.get('date_hired'),
            }
        )
        row['_user_id'] = user.id
        row['_teacher_id'] = teacher.id

    def after_import_row(self, row, row_result, **kwargs):
        if row_result.import_type in ('new', 'update'):
            teacher = row_result.instance
            subject_names = row.get('subjects', '').split('|')
            subject_ids = []
            for name in subject_names:
                name = name.strip()
                if name:
                    try:
                        subject = Subject.objects.get(name=name)
                        subject_ids.append(subject.id)
                    except Subject.DoesNotExist:
                        pass
            teacher.subjects.set(subject_ids)

    def dehydrate_first_name(self, teacher):
        return teacher.user.first_name

    def dehydrate_last_name(self, teacher):
        return teacher.user.last_name

    def dehydrate_email(self, teacher):
        return teacher.user.email

    def dehydrate_subjects(self, teacher):
        return '|'.join([s.name for s in teacher.subjects.all()])


class StudentAdminForm(forms.ModelForm):
    """Custom form for Student admin that handles User creation automatically."""
    first_name = forms.CharField(max_length=150, required=True, help_text="Student's first name")
    last_name = forms.CharField(max_length=150, required=True, help_text="Student's last name")
    email = forms.EmailField(required=True, help_text="Student's email address")
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text="Leave blank to auto-generate a secure random password.",
    )

    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'email', 'password',
            'admission_year', 'admission_form', 'current_class',
            'date_of_birth', 'address',
        ]

    def save(self, commit=True):
        from django.utils import timezone

        admission_year = self.cleaned_data['admission_year'] or timezone.now().year
        admission_form = self.cleaned_data['admission_form'] or 'Form 1'

        # Generate student ID first
        student_id = generate_student_id(
            admission_year=admission_year,
            admission_form=admission_form,
        )

        # Random opaque username — decoupled from student_id to prevent
        # credential enumeration. Students log in via Student ID (handled
        # by StudentIDAuthBackend), not username.
        username = f"stu_{secrets.token_urlsafe(9)}"

        password = self.cleaned_data.get('password') or _generate_random_password()
        user = User.objects.create_user(
            username=username,
            email=self.cleaned_data['email'],
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )

        student = super().save(commit=False)
        student.user = user
        student.student_id = student_id
        student.registration_number = student_id
        student.admission_year = admission_year
        student.admission_form = admission_form
        student.must_change_password = True
        self._initial_password = password

        if commit:
            student.save()
            student.assign_compulsory_subjects()

        return student


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    form = StudentAdminForm
    resource_class = StudentResource
    list_display = (
        'student_id', 'get_full_name', 'current_class',
        'admission_year', 'admission_form', 'created_at',
    )
    list_display_links = ('student_id', 'get_full_name')
    search_fields = (
        'student_id', 'registration_number',
        'user__first_name', 'user__last_name',
    )
    list_filter = ('current_class', 'admission_year', 'admission_form')
    readonly_fields = ('student_id', 'registration_number', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = None  # Use default form layout (no fieldsets for add)

    add_fieldsets = (
        ('Student Details', {
            'fields': (
                'first_name', 'last_name', 'email', 'password',
                'admission_year', 'admission_form', 'current_class',
                'date_of_birth', 'address',
            ),
            'description': 'Student ID will be auto-generated. Students log in using their Student ID and password.',
        }),
    )

    change_fieldsets = (
        ('Student ID (Auto-generated)', {
            'fields': ('student_id',),
        }),
        ('Admission Info', {
            'fields': ('admission_year', 'admission_form', 'current_class'),
        }),
        ('Personal Info', {
            'fields': ('date_of_birth', 'address'),
        }),
        ('System Info', {
            'fields': ('registration_number', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:  # Adding new student
            return self.add_fieldsets
        return self.change_fieldsets

    def get_readonly_fields(self, request, obj=None):
        base = ['student_id', 'registration_number', 'created_at', 'updated_at']
        if obj:
            base.extend(['admission_year', 'admission_form'])
        return base

    def save_model(self, request, obj, form, change):
        if not change:
            request._initial_password = getattr(form, '_initial_password', None)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        password = getattr(request, '_initial_password', None)
        if password:
            self.message_user(
                request,
                f'Student {obj.student_id} created. Initial password: {password}',
            )
        return super().response_add(request, obj, post_url_continue)

    def get_full_name(self, obj):
        try:
            return obj.user.get_full_name() or obj.student_id
        except Exception:
            return obj.student_id or "—"
    get_full_name.short_description = 'Student Name'
    get_full_name.admin_order_field = 'user__first_name'


class TeacherAdminForm(forms.ModelForm):
    """Custom form for Teacher admin that handles User creation automatically."""

    first_name = forms.CharField(max_length=150, required=True, help_text="Teacher's first name")
    last_name = forms.CharField(max_length=150, required=True, help_text="Teacher's last name")
    email = forms.EmailField(required=True, help_text="Teacher's email address")
    password = forms.CharField(
        widget=forms.PasswordInput, required=False,
        help_text="Leave blank to auto-generate a secure random password.",
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Tick the subjects this teacher will teach.",
    )

    class Meta:
        model = Teacher
        fields = [
            'employee_id', 'first_name', 'last_name', 'email', 'password',
            'phone', 'date_hired', 'subjects',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order subjects by class and name for a tidy checklist
        self.fields['subjects'].queryset = Subject.objects.select_related(
            'assigned_class'
        ).order_by('assigned_class__name', 'name')

    def save(self, commit=True):
        teacher = super().save(commit=False)
        user = teacher.user
        if not user or not user.pk:
            username = self.cleaned_data['employee_id']
            user = User(
                username=username,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                email=self.cleaned_data['email'],
            )
            user.set_password(
                self.cleaned_data.get('password') or _generate_random_password()
            )
            user.save()
        else:
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.save()
        teacher.user = user

        if commit:
            teacher.save()
            self.save_m2m()
        return teacher


@admin.register(Teacher)
class TeacherAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    form = TeacherAdminForm
    resource_class = TeacherResource

    list_display = (
        'employee_id', 'get_full_name', 'phone', 'get_subjects_list',
        'date_hired', 'created_at',
    )
    list_display_links = ('employee_id', 'get_full_name')
    list_select_related = ('user',)
    search_fields = (
        'employee_id', 'user__first_name', 'user__last_name', 'user__email',
        'subjects__name', 'subjects__code',
    )
    list_filter = ('subjects__assigned_class', 'subjects', 'date_hired')
    autocomplete_fields = ()
    date_hierarchy = 'date_hired'
    ordering = ('employee_id',)
    save_on_top = True
    list_per_page = 25
    preserve_filters = True

    add_fieldsets = (
        ('Account Login', {
            'fields': (
                'employee_id', 'first_name', 'last_name', 'email', 'password',
            ),
            'description': 'Username = Employee ID. A secure random password is generated if left blank.',
        }),
        ('Profile', {
            'fields': ('phone', 'date_hired'),
        }),
        ('Subjects Taught', {
            'fields': ('subjects',),
            'description': 'Tick the subjects this teacher is assigned to teach.',
        }),
    )

    change_fieldsets = (
        ('Account', {
            'fields': ('employee_id', 'first_name', 'last_name', 'email', 'password'),
            'description': 'Leave the password blank to keep the current password.',
        }),
        ('Profile', {
            'fields': ('phone', 'date_hired'),
        }),
        ('Subjects Taught', {
            'fields': ('subjects',),
        }),
        ('System Info', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.change_fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return ['employee_id', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        try:
            return obj.user.get_full_name() or obj.employee_id
        except Exception:
            return obj.employee_id or "—"
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'

    def get_subjects_list(self, obj):
        names = [s.name for s in obj.subjects.all()[:3]]
        extra = obj.subjects.count() - len(names)
        if extra > 0:
            return ", ".join(names) + f" (+{extra} more)"
        return ", ".join(names) if names else "—"
    get_subjects_list.short_description = 'Subjects'
