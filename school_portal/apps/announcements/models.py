from django.db import models
from django.db import models
from django.contrib.auth.models import User

class Announcement(models.Model):
    AUDIENCE_CHOICES = [
        ('all', 'Everyone'),
        ('students', 'Students Only'),
        ('teachers', 'Teachers Only'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_staff': True})
    target_audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
# Create your models here.
