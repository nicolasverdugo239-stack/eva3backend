import hashlib

from django.db.models import F

from .models import Order, Ingredient, Dispatch
from .roles import has_role, SALES, KITCHEN, WAREHOUSE, DISPATCH


def notification_signature(kind, title, ids):
    identifiers = ",".join(str(pk) for pk in sorted(ids))
    fingerprint = hashlib.sha256(
        identifiers.encode("utf-8")
    ).hexdigest()[:20]

    return f"{kind}:{title}:{fingerprint}"


def get_notifications(user):
    if not user.is_authenticated:
        return []

    notifications = []

    def add(kind, title, message, url, ids):
        ids = list(ids)
        count = len(ids)

        if not count:
            return

        notifications.append({
            "key": notification_signature(kind, title, ids),
            "kind": kind,
            "title": title,
            "message": message,
            "url": url,
            "count": count,
        })

    if has_role(user, SALES):
        ids = Order.objects.filter(
            quote_status=Order.QuoteStatus.SENT
        ).values_list("pk", flat=True)

        add(
            "ventas",
            "Cotizaciones pendientes",
            "Cotizaciones esperando respuesta.",
            "/pedidos/",
            ids,
        )

    if has_role(user, WAREHOUSE):
        ids = Ingredient.objects.filter(
            stock__lte=F("minimum_stock")
        ).values_list("pk", flat=True)

        add(
            "bodega",
            "Inventario bajo",
            "Ingredientes que requieren revisión.",
            "/insumos/",
            ids,
        )

    if has_role(user, KITCHEN):
        ids = Order.objects.filter(
            status__in=[
                Order.Status.PREPARING,
                Order.Status.BAKED,
                Order.Status.QUALITY,
            ]
        ).values_list("pk", flat=True)

        add(
            "cocina",
            "Pedidos en producción",
            "Pedidos en proceso de producción.",
            "/pedidos/",
            ids,
        )

    if has_role(user, DISPATCH):
        ids = Order.objects.filter(
            status=Order.Status.READY
        ).values_list("pk", flat=True)

        add(
            "despacho",
            "Pedidos listos",
            "Pedidos listos para despacho.",
            "/despachos/",
            ids,
        )

        ids = Dispatch.objects.filter(
            status__in=[
                Dispatch.Status.PLANNED,
                Dispatch.Status.IN_ROUTE,
            ]
        ).values_list("pk", flat=True)

        add(
            "despacho",
            "Despachos pendientes",
            "Despachos programados o en ruta.",
            "/despachos/",
            ids,
        )

    return notifications
