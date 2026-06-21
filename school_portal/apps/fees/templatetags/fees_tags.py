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
    # superuser already has accountant access via decorator
    if user.is_superuser:
        return True
    if hasattr(user, "accountant"):
        return True
    return user.groups.filter(name="Accountant").exists()
