"""
Signal handlers for the fees module.

When the fees app is ready, we ensure that:

* the ``Accountant`` permission group exists, and
* each ``Accountant`` profile is automatically added to that group
  (and removed when the profile is deleted).
"""
import logging

from django.contrib.auth.models import Group
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Accountant
from .decorators import ACCOUNTANT_GROUP

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Accountant)
def add_to_accountant_group(sender, instance, created, **kwargs):
    """Ensure the linked Django user belongs to the Accountant group."""
    if not instance.user:
        return
    group, _ = Group.objects.get_or_create(name=ACCOUNTANT_GROUP)
    if not instance.user.groups.filter(pk=group.pk).exists():
        instance.user.groups.add(group)
        logger.info("Added user %s to Accountant group", instance.user.username)


@receiver(post_delete, sender=Accountant)
def remove_from_accountant_group(sender, instance, **kwargs):
    """Remove the user from the Accountant group when their profile is deleted.

    We don't remove superuser/staff status — that's an admin decision.
    """
    if not instance.user:
        return
    try:
        group = Group.objects.get(name=ACCOUNTANT_GROUP)
        instance.user.groups.remove(group)
    except Group.DoesNotExist:
        pass
