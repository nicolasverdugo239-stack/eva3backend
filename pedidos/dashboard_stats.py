
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Order


def get_dashboard_charts():
    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    # Pedidos creados durante los últimos 7 días
    daily_counts = (
        Order.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("pk"))
        .order_by("day")
    )

    counts_by_day = {
        item["day"]: item["total"]
        for item in daily_counts
    }

    days = [
        start_date + timedelta(days=i)
        for i in range(7)
    ]

    orders_chart = {
        "labels": [day.strftime("%d/%m") for day in days],
        "values": [counts_by_day.get(day, 0) for day in days],
    }

    # Distribución de pedidos por estado
    status_counts = dict(
        Order.objects
        .values("status")
        .annotate(total=Count("pk"))
        .values_list("status", "total")
    )

    status_chart = {
        "labels": [label for _, label in Order.Status.choices],
        "values": [
            status_counts.get(status, 0)
            for status, _ in Order.Status.choices
        ],
    }

    return {
        "orders_chart": orders_chart,
        "status_chart": status_chart,
    }
