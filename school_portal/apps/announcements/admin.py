from django.contrib import admin
from django.contrib import admin
from .models import Announcement

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'target_audience', 'created_at')
    list_filter = ('target_audience', 'created_at')
    search_fields = ('title', 'content')
# Register your models here.
