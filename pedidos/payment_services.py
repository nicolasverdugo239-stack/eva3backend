from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import Order, Payment
from .roles import SALES, has_role


@transaction.atomic
def register_payment(*, order_id, amount, method, user, reference=""):
    """Registra un abono validando el saldo bajo bloqueo."""

    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status == Order.Status.CANCELLED:
        raise ValidationError("No se pueden registrar pagos en pedidos cancelados.")

    if order.sale_price is None:
        raise ValidationError("Primero debes registrar el precio de venta.")

    if not user or not user.is_authenticated or not user.is_active:
        raise ValidationError("Debes iniciar sesión para registrar pagos.")

    if not has_role(user, SALES):
        raise ValidationError("Solo Ventas o Administración puede registrar pagos.")

    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError, ArithmeticError):
        raise ValidationError("El monto ingresado no es válido.")

    if not amount.is_finite() or amount <= 0:
        raise ValidationError("El abono debe ser mayor que cero.")

    if amount.as_tuple().exponent < -2:
        raise ValidationError("El abono admite como máximo dos decimales.")

    valid_methods = Payment.Method.values
    if method not in valid_methods:
        raise ValidationError("El método de pago no es válido.")

    total_paid = (
        Payment.objects.filter(order=order).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    balance = order.sale_price - total_paid

    if amount > balance:
        raise ValidationError(
            f"El abono supera el saldo pendiente de ${balance}."
        )

    payment = Payment(
        order=order,
        amount=amount,
        method=method,
        reference=reference,
        created_by=user,
    )

    payment.full_clean()
    payment.save()

    return payment
