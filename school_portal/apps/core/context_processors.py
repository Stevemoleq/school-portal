from apps.announcements.models import Announcement


def notification_context(request):
    recent = []
    unread_count = 0
    unread_announcements = 0

    if not request.user.is_authenticated:
        return {
            "recent_notifications": recent,
            "unread_notification_count": unread_count,
            "unread_announcements": unread_announcements,
        }

    if hasattr(request.user, "parent"):
        parent = request.user.parent
        qs = parent.notifications.all().order_by("-created_at")
        unread_count = qs.filter(status__in=["sent", "pending"]).count()
        recent = qs[:5]

        unread_announcements = Announcement.objects.filter(
            target_audience__in=["all", "parents"]
        ).exclude(
            read_by_parents__parent=parent
        ).count()

    return {
        "recent_notifications": recent,
        "unread_notification_count": unread_count,
        "unread_announcements": unread_announcements,
    }
