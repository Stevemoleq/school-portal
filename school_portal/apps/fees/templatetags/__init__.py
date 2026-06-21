"""
Custom template tags for the fees module.
"""
from django import template

register = template.Library()


@register.filter(name="is_accountant")
def is_accountant(user):
    """Return True if the user has the Accountant role."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return False  # superusers are routed to the admin sidebar
    if hasattr(user, "accountant"):
        return True
    return user.groups.filter(name="Accountant").exists()
