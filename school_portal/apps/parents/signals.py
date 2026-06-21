"""Signal handlers for the parents module.

Auto-marks in-app notifications as "sent" immediately on creation
since they don't require external delivery (SMS/email).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import ParentNotification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ParentNotification)
def auto_deliver_in_app_notifications(sender, instance, created, **kwargs):
    """Mark in-app notifications as sent immediately.

    SMS and email notifications remain 'pending' — they require
    a real delivery channel (Twilio, SendGrid, etc.) to be wired up.
    """
    if created and instance.notification_type == 'in_app' and instance.status == 'pending':
        instance.status = 'sent'
        instance.sent_at = timezone.now()
        instance.save(update_fields=['status', 'sent_at'])
