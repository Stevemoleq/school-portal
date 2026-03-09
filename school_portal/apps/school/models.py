from django.db import models
from django.db import models

class Class(models.Model):
    name = models.CharField(max_length=50, unique=True)
    section = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return f"{self.name} ({self.code})"
# Create your models here.
