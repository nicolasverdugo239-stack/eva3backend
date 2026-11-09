from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Ingredient, InventoryMovement, Order, OrderStatusHistory

KANBAN_STATUSES = [
    Order.Status.RECEIVED,
    Order.Status.PREPARING,
    Order.Status.BAKED,
    Order.Status.QUALITY,
    Order.Status.READY,
]


@transaction.atomic
def register_inventory_movement(ingredient_id, direction, quantity, note, user):
    if direction not in InventoryMovement.Direction.values:
        raise ValidationError("Selecciona Entrada o Salida.")
    if quantity <= 0:
        raise ValidationError("La cantidad debe ser mayor que cero.")
    ingredient = Ingredient.objects.select_for_update().get(pk=ingredient_id)
    if direction == InventoryMovement.Direction.OUT and ingredient.stock < quantity:
        raise ValidationError(
            f"Stock insuficiente: disponible {ingredient.stock} {ingredient.unit}, requerido {quantity}."
        )
    if direction == InventoryMovement.Direction.IN:
        ingredient.stock += quantity
    else:
        ingredient.stock -= quantity
    ingredient.save(update_fields=["stock", "updated_at"])
    return InventoryMovement.objects.create(
        ingredient=ingredient,
        direction=direction,
        quantity=quantity,
        stock_after=ingredient.stock,
        source=InventoryMovement.Source.MANUAL,
        note=note,
        created_by=user,
    )


@transaction.atomic
def transition_quote(order_id, new_status):
    order = Order.objects.select_for_update().get(pk=order_id)
    permitted = {
        Order.QuoteStatus.SENT: {Order.QuoteStatus.DRAFT},
        Order.QuoteStatus.APPROVED: {Order.QuoteStatus.SENT},
        Order.QuoteStatus.REJECTED: {Order.QuoteStatus.SENT},
        Order.QuoteStatus.DRAFT: {Order.QuoteStatus.REJECTED},
    }
    if new_status not in permitted or order.quote_status not in permitted[new_status]:
        raise ValidationError("Transición de cotización no permitida.")
    if new_status == Order.QuoteStatus.SENT and not order.materials.exists():
        raise ValidationError("Agrega al menos un insumo BOM antes de enviar la cotización.")
    order.quote_status = new_status
    order.save(update_fields=["quote_status", "updated_at"])
    return order


@transaction.atomic
def transition_order(order_id, new_status, user):
    order = Order.objects.select_for_update().get(pk=order_id)
    if new_status == Order.Status.CANCELLED:
        if order.status in (Order.Status.READY, Order.Status.CANCELLED):
            raise ValidationError("No se puede cancelar un pedido listo o ya cancelado.")
        if order.inventory_reserved:
            lines = list(order.materials.all())
            ingredient_ids = sorted({line.ingredient_id for line in lines})
            ingredients = {
                item.pk: item
                for item in Ingredient.objects.select_for_update().filter(pk__in=ingredient_ids).order_by("pk")
            }
            returned = {}
            for line in lines:
                returned[line.ingredient_id] = returned.get(line.ingredient_id, 0) + line.quantity
            for ingredient_id, quantity in returned.items():
                ingredient = ingredients[ingredient_id]
                ingredient.stock += quantity
                ingredient.save(update_fields=["stock", "updated_at"])
                InventoryMovement.objects.create(
                    ingredient=ingredient,
                    direction=InventoryMovement.Direction.IN,
                    quantity=quantity,
                    stock_after=ingredient.stock,
                    source=InventoryMovement.Source.CANCELLATION,
                    order=order,
                    note=f"Devolución por cancelación de {order.number}",
                    created_by=user,
                )
            order.inventory_reserved = False
    else:
        if order.status == Order.Status.CANCELLED or order.status not in KANBAN_STATUSES:
            raise ValidationError("El pedido no puede avanzar desde su estado actual.")
        if order.quote_status != Order.QuoteStatus.APPROVED:
            raise ValidationError("La cotización debe estar aprobada antes de iniciar la producción.")
        current_index = KANBAN_STATUSES.index(order.status)
        expected_status = KANBAN_STATUSES[current_index + 1] if current_index < len(KANBAN_STATUSES) - 1 else None
        if new_status != expected_status:
            raise ValidationError("El pedido debe avanzar al siguiente estado del tablero.")
        if new_status == Order.Status.PREPARING and not order.inventory_reserved:
            lines = list(order.materials.select_related("ingredient"))
            if not lines:
                raise ValidationError("Agrega al menos un insumo a la lista BOM antes de iniciar la producción.")
            ingredient_ids = sorted({line.ingredient_id for line in lines})
            ingredients = {
                item.pk: item
                for item in Ingredient.objects.select_for_update().filter(pk__in=ingredient_ids).order_by("pk")
            }
            required = {}
            for line in lines:
                required[line.ingredient_id] = required.get(line.ingredient_id, 0) + line.quantity
            unavailable = [
                f"{ingredients[ingredient_id].name}: disponible {ingredients[ingredient_id].stock} "
                f"{ingredients[ingredient_id].unit}, requerido {quantity}"
                for ingredient_id, quantity in required.items()
                if ingredients[ingredient_id].stock < quantity
            ]
            if unavailable:
                raise ValidationError("Stock insuficiente: " + "; ".join(unavailable))
            for ingredient_id, quantity in required.items():
                ingredient = ingredients[ingredient_id]
                ingredient.stock -= quantity
                ingredient.save(update_fields=["stock", "updated_at"])
                InventoryMovement.objects.create(
                    ingredient=ingredient,
                    direction=InventoryMovement.Direction.OUT,
                    quantity=quantity,
                    stock_after=ingredient.stock,
                    source=InventoryMovement.Source.PRODUCTION,
                    order=order,
                    note=f"Consumo BOM al iniciar producción de {order.number}",
                    created_by=user,
                )
            order.inventory_reserved = True

    previous_status = order.status
    order.status = new_status
    order.save(update_fields=["status", "inventory_reserved", "updated_at"])
    OrderStatusHistory.objects.create(
        order=order, previous_status=previous_status, new_status=new_status, changed_by=user
    )
    return order
