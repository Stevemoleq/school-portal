from django import forms
from .models import Class, Subject


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'section']


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'class_id']
