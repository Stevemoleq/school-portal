"""
Access-control decorators for the fees module.

The Accountant role is implemented using both:

* a per-user ``Accountant`` profile (mirrors ``Teacher`` / ``Parent``), and
* a Django ``Group`` named ``Accountant`` that grants the appropriate
  permissions (created automatically by ``apps.fees.signals``).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.models import Group
from django.shortcuts import redirect


ACCOUNTANT_GROUP = "Accountant"


def get_or_create_accountant_group():
    """Return the Accountant permission group, creating it if missing."""
    group, _ = Group.objects.get_or_create(name=ACCOUNTANT_GROUP)
    return group


def user_is_accountant(user):
    """Return True if the user has the Accountant role."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if hasattr(user, "accountant"):
        return True
    return user.groups.filter(name=ACCOUNTANT_GROUP).exists()


def accountant_required(view_func):
    """Allow only Accountants (and superusers) to access the view."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not user_is_accountant(request.user):
            messages.error(
                request,
                "Access denied. Accountant privileges are required.",
            )
            return redirect("dashboard_redirect")
        return view_func(request, *args, **kwargs)

    return _wrapped
