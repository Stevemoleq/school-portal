from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Accountant, AuditLog, FeeConfiguration, Receipt


@admin.register(Accountant)
class AccountantAdmin(admin.ModelAdmin):
    list_display = ("accountant_id", "get_full_name", "phone", "created_at")
    list_display_links = ("accountant_id", "get_full_name")
    search_fields = ("accountant_id", "user__first_name", "user__last_name", "user__username", "phone")
    readonly_fields = ("accountant_id", "created_at", "updated_at")
    autocomplete_fields = ["user"]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "user__first_name"


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "student_id", "student_name", "amount", "balance_after", "term", "academic_year", "date_issued", "issued_by")
    list_filter = ("term", "academic_year", "date_issued")
    search_fields = ("receipt_number", "student_id", "student_name", "payment__transaction_reference")
    readonly_fields = ("receipt_number", "date_issued")
    date_hierarchy = "date_issued"
    autocomplete_fields = ["payment", "invoice", "issued_by"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "actor", "actor_role", "target_model", "target_id", "description_short")
    list_filter = ("action", "actor_role", "target_model", "timestamp")
    search_fields = ("description", "actor__username", "target_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def description_short(self, obj):
        return (obj.description or "")[:80]
    description_short.short_description = "Description"


@admin.register(FeeConfiguration)
class FeeConfigurationAdmin(admin.ModelAdmin):
    list_display = ("school_name", "school_phone", "school_email", "updated_at")

    def has_add_permission(self, request):
        return not FeeConfiguration.objects.exists()
