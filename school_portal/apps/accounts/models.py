from django.db import models
from django.contrib.auth.models import User


# Module-level mapping: subject name -> category code. Used by the
# Subject.save() hook and by the data migration. Anything not listed
# falls back to OTHER. The values are plain strings rather than
# references to Subject.CATEGORY_* to avoid forward-reference errors
# (this module is loaded before the Subject class is defined).
_CATEGORY_BY_NAME = {
    # Science
    'Physics': 'SCIENCE',
    'Chemistry': 'SCIENCE',
    'Biology': 'SCIENCE',
    'Agriculture': 'SCIENCE',
    'Computer Studies': 'SCIENCE',
    'Science': 'SCIENCE',
    # Humanities
    'History': 'HUMANITIES',
    'Geography': 'HUMANITIES',
    'Bible Knowledge': 'HUMANITIES',
    'Bible': 'HUMANITIES',
    'Religious Education': 'HUMANITIES',
    'Social Studies': 'HUMANITIES',
    'Chichewa': 'HUMANITIES',
    'English': 'HUMANITIES',
    # Commercial
    'Commerce': 'COMMERCIAL',
    'Accounting': 'COMMERCIAL',
    'Business Studies': 'COMMERCIAL',
    'Economics': 'COMMERCIAL',
    # Technical
    'Technical Drawing': 'TECHNICAL',
    'Woodwork': 'TECHNICAL',
    'Metalwork': 'TECHNICAL',
    'Home Economics': 'TECHNICAL',
    # Core
    'Mathematics': 'CORE',
}


class Class(models.Model):
    name = models.CharField(max_length=50, unique=True)
    section = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'classes'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} {self.section}".strip()


class Subject(models.Model):
    CATEGORY_CORE = 'CORE'
    CATEGORY_SCIENCE = 'SCIENCE'
    CATEGORY_HUMANITIES = 'HUMANITIES'
    CATEGORY_COMMERCIAL = 'COMMERCIAL'
    CATEGORY_TECHNICAL = 'TECHNICAL'
    CATEGORY_OTHER = 'OTHER'

    CATEGORY_CHOICES = [
        (CATEGORY_CORE, 'Core / Compulsory'),
        (CATEGORY_SCIENCE, 'Science'),
        (CATEGORY_HUMANITIES, 'Humanities'),
        (CATEGORY_COMMERCIAL, 'Commercial'),
        (CATEGORY_TECHNICAL, 'Technical'),
        (CATEGORY_OTHER, 'Other'),
    ]

    # Compulsory subjects every student must take
    COMPULSORY_SUBJECTS = {
        'English': 'ENG',
        'Mathematics': 'MATH',
        'Chichewa': 'CHIC',
        'Biology': 'BIO',
    }

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    assigned_class = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name='subjects'
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER, db_index=True,
    )
    is_compulsory = models.BooleanField(
        default=False, db_index=True,
        help_text="Compulsory subjects are automatically assigned to every student.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_compulsory', 'category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        # Keep is_compulsory in sync with the canonical compulsory list
        if self.name in self.COMPULSORY_SUBJECTS:
            self.is_compulsory = True
            if not self.category or self.category == self.CATEGORY_OTHER:
                self.category = self.CATEGORY_CORE
        else:
            # Auto-categorise electives by their name. The mapping lives
            # in CATEGORY_BY_NAME below; the data migration uses the
            # same map.
            auto = _CATEGORY_BY_NAME.get(self.name)
            if auto and (not self.category or self.category == self.CATEGORY_OTHER):
                self.category = auto
        super().save(*args, **kwargs)


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')

    # Student ID (auto-generated, permanent, immutable)
    student_id = models.CharField(
        max_length=25, unique=True, db_index=True,
        help_text="Auto-generated Student ID (e.g., NZS-26-F1-0001). Cannot be changed.",
        editable=False,
    )

    # Admission info (set once at creation, never changes)
    admission_year = models.PositiveIntegerField(
        help_text="Year of admission (e.g., 2026)",
        null=True, blank=True,
    )
    admission_form = models.CharField(
        max_length=50, blank=True,
        help_text="Form/class at time of admission (e.g., Form 1)",
    )

    # Current class (changes when student is promoted)
    current_class = models.ForeignKey(
        Class, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='students',
        help_text="Current class assignment (can change with promotions)",
    )

    # Personal info
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    # Force password change on next login (set by admin on creation/reset)
    must_change_password = models.BooleanField(
        default=False, editable=False,
        help_text="Student must change password on next login.",
    )

    # Legacy field — kept for backward compatibility during migration
    registration_number = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text="Legacy registration number. Kept for backward compatibility.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_id']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        try:
            name = self.user.get_full_name()
            return f"{name} ({self.student_id})" if self.student_id else name
        except Exception:
            return self.student_id or f"Student #{self.pk}"

    def save(self, *args, **kwargs):
        # Track class change for promotion
        if self.pk:
            try:
                old = Student.objects.get(pk=self.pk)
                class_changed = old.current_class_id != self.current_class_id
            except Student.DoesNotExist:
                class_changed = False
        else:
            class_changed = False

        # Auto-generate student_id on first save
        if not self.student_id:
            from .student_id import generate_student_id
            self.student_id = generate_student_id(
                admission_year=self.admission_year,
                admission_form=self.admission_form,
            )

        # Keep registration_number in sync for backward compatibility
        if not self.registration_number:
            self.registration_number = self.student_id

        super().save(*args, **kwargs)

        # Re-assign compulsory subjects when promoted to a new class
        if class_changed:
            self.assign_compulsory_subjects()

    @property
    def form_display(self):
        """Compact form code for display."""
        from .student_id import get_form_display
        return get_form_display(self.admission_form) if self.admission_form else "-"

    @property
    def is_new(self):
        """Check if this is a new student (not yet saved)."""
        return self.pk is None

    @property
    def assigned_subjects(self):
        """All subjects this student is currently taking (compulsory + elective)."""
        qs = Subject.objects.filter(student_subjects__student=self)
        if self.current_class:
            qs = qs.filter(assigned_class=self.current_class)
        return qs.distinct()

    def compulsory_subjects(self):
        return self.assigned_subjects.filter(is_compulsory=True)

    def elective_subjects(self):
        return self.assigned_subjects.filter(is_compulsory=False)

    def assign_compulsory_subjects(self):
        """Ensure this student is enrolled in every compulsory subject.

        Safe to call multiple times — duplicates are prevented by the
        unique_together constraint on StudentSubject.
        """
        from .models import StudentSubject  # local to avoid circular import
        compulsory = Subject.objects.filter(is_compulsory=True)
        for subject in compulsory:
            StudentSubject.objects.get_or_create(
                student=self, subject=subject,
                defaults={'is_elective': False},
            )
        return compulsory.count()

    def assign_subject(self, subject, is_elective=True):
        """Assign a single subject to this student."""
        from .models import StudentSubject
        ss, created = StudentSubject.objects.get_or_create(
            student=self, subject=subject,
            defaults={'is_elective': is_elective},
        )
        return ss, created

    def remove_subject(self, subject):
        """Remove a subject assignment. Compulsory subjects are protected."""
        if subject.is_compulsory:
            return False, "Compulsory subjects cannot be removed."
        from .models import StudentSubject
        deleted, _ = StudentSubject.objects.filter(
            student=self, subject=subject
        ).delete()
        return bool(deleted), None

    def is_enrolled_in(self, subject):
        return StudentSubject.objects.filter(
            student=self, subject=subject
        ).exists()

    def registered_subjects_for_term(self, term):
        """Return subjects registered for a specific AcademicTerm, filtered to the student's class."""
        qs = Subject.objects.filter(
            term_registrations__student=self,
            term_registrations__term=term,
        )
        if self.current_class:
            qs = qs.filter(assigned_class=self.current_class)
        return qs.distinct()

    def register_for_term(self, term, subject_ids):
        """Register for a set of subjects in a given term.

        Existing registrations for the term are replaced with the given
        subject IDs. Compulsory subjects for the student's class are
        always included regardless.
        """
        from .models import SubjectRegistration
        compulsory_qs = Subject.objects.filter(is_compulsory=True)
        if self.current_class:
            compulsory_qs = compulsory_qs.filter(assigned_class=self.current_class)
        compulsory_ids = list(compulsory_qs.values_list('id', flat=True))
        all_ids = set(subject_ids) | set(compulsory_ids)
        SubjectRegistration.objects.filter(student=self, term=term).delete()
        objs = [
            SubjectRegistration(student=self, subject_id=sid, term=term)
            for sid in all_ids
        ]
        SubjectRegistration.objects.bulk_create(objs, ignore_conflicts=True)
        return len(objs)

    def available_terms(self):
        """Return all AcademicTerms this student has registrations or results for."""
        term_ids = set(
            self.subject_registrations.values_list('term_id', flat=True)
        )
        from apps.results.models import Result
        result_pairs = set(
            Result.objects.filter(student=self)
            .values_list('session', 'term')
            .distinct()
        )
        query = models.Q(id__in=term_ids)
        for session, term in result_pairs:
            query |= models.Q(session=session, term=term)
        return AcademicTerm.objects.filter(query).distinct().order_by('-session', 'term')


class StudentSubject(models.Model):
    """Through model linking a student to a subject they take.

    A student may take many subjects; a subject may have many students.
    Constraints:
        - Unique (student, subject) — no duplicate assignments.
        - Indexed for fast lookups by student and by subject.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='student_subjects'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='student_subjects'
    )
    is_elective = models.BooleanField(
        default=False,
        help_text="True if added as an elective (not a compulsory subject).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('student', 'subject')]
        ordering = ['subject__name']
        indexes = [
            models.Index(fields=['student', 'subject']),
            models.Index(fields=['subject', 'student']),
        ]
        verbose_name = 'Student Subject'
        verbose_name_plural = 'Student Subjects'

    def __str__(self):
        return f"{self.student} → {self.subject}"

    @property
    def is_compulsory(self):
        return self.subject.is_compulsory


class AcademicTerm(models.Model):
    TERM_CHOICES = [
        ('1st', 'First Term'),
        ('2nd', 'Second Term'),
        ('3rd', 'Third Term'),
    ]
    term = models.CharField(max_length=3, choices=TERM_CHOICES, db_index=True)
    session = models.CharField(
        max_length=9,
        help_text="Academic session, e.g. 2025-2026",
        db_index=True,
    )
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(
        default=False,
        help_text="Only one term should be active at a time.",
    )
    registration_open = models.BooleanField(
        default=False,
        help_text="Students can register subjects when this is enabled.",
    )
    registration_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional deadline — registration auto-closes after this date.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('term', 'session')]
        ordering = ['-session', 'term']
        verbose_name = 'Academic Term'
        verbose_name_plural = 'Academic Terms'

    def save(self, *args, **kwargs):
        if not self.name:
            term_display = dict(self.TERM_CHOICES).get(self.term, self.term)
            self.name = f"{term_display} {self.session}"
        if self.is_active:
            AcademicTerm.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SubjectRegistration(models.Model):
    """Per-term enrollment: which subjects a student is taking this term."""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='subject_registrations'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='term_registrations'
    )
    term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name='registrations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('student', 'subject', 'term')]
        indexes = [
            models.Index(fields=['student', 'term']),
            models.Index(fields=['term', 'subject']),
        ]
        ordering = ['term', 'subject__name']
        verbose_name = 'Subject Registration'
        verbose_name_plural = 'Subject Registrations'

    def __str__(self):
        return f"{self.student} → {self.subject} ({self.term.name})"


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher')
    employee_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='teachers')
    date_hired = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_id']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"
