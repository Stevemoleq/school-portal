from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
#from apps.accounts.models import Student, Subject
from apps.accounts.models import Student
from apps.school.models import Subject

class Result(models.Model):
    TERM_CHOICES = [
        ('1st', 'First Term'),
        ('2nd', 'Second Term'),
        ('3rd', 'Third Term'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    marks = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Marks must be between 0 and 100"
    )
    grade = models.CharField(max_length=2, blank=True)  # Could auto-calc
    term = models.CharField(max_length=3, choices=TERM_CHOICES)
    session = models.CharField(max_length=9)  # e.g., "2024-2025"
    date_uploaded = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ['student', 'subject', 'term', 'session']

    def save(self, *args, **kwargs):
        # Validate marks are within range
        if self.marks < 0 or self.marks > 100:
            raise ValueError("Marks must be between 0 and 100")
        
        # Simple grade calculation based on marks
        if self.marks >= 75:
            self.grade = 'A'
        elif self.marks >= 60:
            self.grade = 'B'
        elif self.marks >= 50:
            self.grade = 'C'
        elif self.marks >= 40:
            self.grade = 'D'
        else:
            self.grade = 'F'
        super().save(*args, **kwargs)
# Create your models here.
