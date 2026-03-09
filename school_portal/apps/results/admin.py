from django.contrib import admin
from django.contrib import admin
from .models import Result

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'marks', 'grade', 'term', 'session', 'is_published')
    list_filter = ('term', 'session', 'is_published', 'subject')
    search_fields = ('student__registration_number', 'student__user__first_name', 'subject__name')
# Register your models here.
