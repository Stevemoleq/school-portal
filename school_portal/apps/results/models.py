from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import Student, Subject


GRADE_THRESHOLDS = [
    ('A', 75),
    ('B', 60),
    ('C', 50),
    ('D', 40),
]


class Result(models.Model):
    TERM_CHOICES = [
        ('1st', 'First Term'),
        ('2nd', 'Second Term'),
        ('3rd', 'Third Term'),
    ]
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='results'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='results'
    )
    marks = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Marks must be between 0 and 100"
    )
    grade = models.CharField(max_length=2, blank=True)
    term = models.CharField(max_length=3, choices=TERM_CHOICES, db_index=True)
    session = models.CharField(max_length=9, db_index=True)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ['student', 'subject', 'term', 'session']
        indexes = [
            models.Index(fields=['student', 'term', 'session']),
            models.Index(fields=['subject', 'term', 'session']),
            models.Index(fields=['-date_uploaded']),
        ]
        ordering = ['-date_uploaded']

    def save(self, *args, **kwargs):
        if self.marks < 0 or self.marks > 100:
            raise ValueError("Marks must be between 0 and 100")

        self.grade = 'F'
        for grade, threshold in GRADE_THRESHOLDS:
            if self.marks >= threshold:
                self.grade = grade
                break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.subject}: {self.marks} ({self.grade})"
