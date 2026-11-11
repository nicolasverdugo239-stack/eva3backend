from .notifications import get_notifications
from .models import NotificationRead


def notification_context(request):
    if not request.user.is_authenticated:
        return {
            "user_notifications": [],
            "notification_count": 0,
        }

    notifications = get_notifications(request.user)

    keys = [item["key"] for item in notifications]

    read_keys = set(
        NotificationRead.objects.filter(
            user=request.user,
            notification_key__in=keys,
        ).values_list("notification_key", flat=True)
    )

    unread_count = 0

    for notification in notifications:
        notification["is_read"] = notification["key"] in read_keys

        if not notification["is_read"]:
            unread_count += 1

    return {
        "user_notifications": notifications,
        "notification_count": unread_count,
    }
