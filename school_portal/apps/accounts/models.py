from django.db import models
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    registration_number = models.CharField(max_length=20, unique=True)
    student_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True,blank =True, related_name='students')
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.registration_number}"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher')
    employee_id = models.CharField(max_length=20, unique=True)   # <-- fixed
    phone = models.CharField(max_length=15, blank=True)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='teachers')
    date_hired = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

# Signal to auto-create profiles when User is created (optional)
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # We'll handle via admin forms, but can add logic here
        pass
# Create your models here.
