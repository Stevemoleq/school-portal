from django.contrib import admin
from django.contrib.auth.models import User
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, DateWidget
from .models import Student, Teacher
from apps.school.models import Class, Subject

# ---------- Student Resource (unchanged) ----------
class StudentResource(resources.ModelResource):
    first_name = fields.Field(attribute='first_name', column_name='first_name')
    last_name = fields.Field(attribute='last_name', column_name='last_name')
    email = fields.Field(attribute='email', column_name='email')
    student_class = fields.Field(
        column_name='class_name',
        attribute='student_class',
        widget=ForeignKeyWidget(Class, 'name')
    )
    date_of_birth = fields.Field(attribute='date_of_birth', column_name='date_of_birth', widget=DateWidget())
    address = fields.Field(attribute='address', column_name='address')

    class Meta:
        model = Student
        import_id_fields = ('registration_number',)
        fields = ('registration_number', 'first_name', 'last_name', 'email',
                  'student_class', 'date_of_birth', 'address')
        skip_unchanged = True

    def before_import_row(self, row, **kwargs):
        username = row['registration_number']
        first_name = row.get('first_name', '')
        last_name = row.get('last_name', '')
        email = row.get('email', '')
        password = 'defaultpassword'

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

    def dehydrate_first_name(self, student):
        return student.user.first_name

    def dehydrate_last_name(self, student):
        return student.user.last_name

    def dehydrate_email(self, student):
        return student.user.email


# ---------- Teacher Resource (new) ----------
class TeacherResource(resources.ModelResource):
    first_name = fields.Field(attribute='first_name', column_name='first_name')
    last_name = fields.Field(attribute='last_name', column_name='last_name')
    email = fields.Field(attribute='email', column_name='email')
    employee_id = fields.Field(attribute='employee_id', column_name='employee_id')
    phone = fields.Field(attribute='phone', column_name='phone')
    date_hired = fields.Field(attribute='date_hired', column_name='date_hired', widget=DateWidget())
    subjects = fields.Field(attribute='subjects', column_name='subjects')  # will be handled separately

    class Meta:
        model = Teacher
        import_id_fields = ('employee_id',)
        fields = ('employee_id', 'first_name', 'last_name', 'email', 'phone', 'date_hired', 'subjects')
        skip_unchanged = True
        export_order = ('employee_id', 'first_name', 'last_name', 'email', 'phone', 'date_hired', 'subjects')

    def before_import_row(self, row, **kwargs):
        # Create or get the User using employee_id as username
        username = row['employee_id']
        first_name = row.get('first_name', '')
        last_name = row.get('last_name', '')
        email = row.get('email', '')
        password = 'defaultpassword'

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
        
        # Create the Teacher instance with the user
        teacher, teacher_created = Teacher.objects.get_or_create(
            employee_id=row['employee_id'],
            defaults={
                'user': user,
                'phone': row.get('phone', ''),
                'date_hired': row.get('date_hired'),
            }
        )
        
        # Store IDs for later use
        row['_user_id'] = user.id
        row['_teacher_id'] = teacher.id

    def after_import_row(self, row, row_result, **kwargs):
        # Handle many-to-many subjects
        if row_result.import_type in ('new', 'update'):
            teacher = row_result.instance
            subject_names = row.get('subjects', '').split('|')  # assume subjects separated by pipe
            subject_ids = []
            for name in subject_names:
                name = name.strip()
                if name:
                    try:
                        subject = Subject.objects.get(name=name)
                        subject_ids.append(subject.id)
                    except Subject.DoesNotExist:
                        # Optionally create missing subjects? For now, skip.
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


# ---------- Student Admin ----------
@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = StudentResource
    list_display = ('registration_number', 'user', 'student_class')
    search_fields = ('registration_number', 'user__first_name')


# ---------- Teacher Admin (with import/export) ----------
@admin.register(Teacher)
class TeacherAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = TeacherResource
    list_display = ('employee_id', 'user', 'phone')
    search_fields = ('employee_id', 'user__first_name')
    filter_horizontal = ('subjects',)   # makes subject selection easier
