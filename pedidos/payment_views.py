from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Order
from .payment_forms import PaymentForm
from .payment_services import register_payment
from .roles import SALES, role_required


@role_required(SALES)
@require_POST
def order_payment_create(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = PaymentForm(request.POST)

    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect("order_detail", pk=order.pk)

    try:
        payment = register_payment(
            order_id=order.pk,
            amount=form.cleaned_data["amount"],
            method=form.cleaned_data["method"],
            reference=form.cleaned_data["reference"],
            user=request.user,
        )
    except ValidationError as exc:
        for error in exc.messages:
            messages.error(request, error)
    else:
        messages.success(
            request,
            f"Abono de ${payment.amount} registrado correctamente.",
        )

    return redirect("order_detail", pk=order.pk)
