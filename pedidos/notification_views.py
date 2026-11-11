from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .models import NotificationRead
from .notifications import get_notifications


@login_required
@require_POST
def mark_notification_read(request):
    key = request.POST.get("notification_key", "")

    notifications = get_notifications(request.user)

    valid_keys = {
        item["key"]
        for item in notifications
    }

    if key not in valid_keys:
        raise Http404("Notificación no encontrada.")

    NotificationRead.objects.update_or_create(
        user=request.user,
        notification_key=key,
        defaults={},
    )

    return redirect("dashboard")
