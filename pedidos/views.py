from .dashboard_stats import get_dashboard_charts
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CustomerForm,
    DispatchForm,
    IngredientForm,
    InventoryMovementForm,
    MaterialFormSet,
    OrderForm,
)
from .models import Customer, Dispatch, Ingredient, InventoryMovement, Order, OrderStatusHistory
from .roles import DISPATCH as DISPATCH_ROLE, KITCHEN, SALES, WAREHOUSE, has_role, role_required
from .services import KANBAN_STATUSES, transition_order, transition_quote


@login_required
def dashboard(request):
    orders = Order.objects.select_related("customer")
    context = {
        "orders": orders.exclude(status=Order.Status.CANCELLED)[:8],
        "orders_count": orders.exclude(status=Order.Status.CANCELLED).count(),
        "pending_quotes": orders.filter(quote_status=Order.QuoteStatus.SENT).count(),
        "production_count": orders.filter(
            status__in=[Order.Status.PREPARING, Order.Status.BAKED, Order.Status.QUALITY]
        ).count(),
        "low_stock": Ingredient.objects.filter(stock__lte=F("minimum_stock")).count(),
        "ready_to_dispatch": orders.filter(status=Order.Status.READY).count(),
        "dispatches_scheduled": Dispatch.objects.filter(
            status__in=[Dispatch.Status.PLANNED, Dispatch.Status.IN_ROUTE]
        ).count(),
        "deliveries_completed": Dispatch.objects.filter(status=Dispatch.Status.DELIVERED).count(),
    }
    context.update(get_dashboard_charts())
    return render(request, "pedidos/dashboard.html", context)

@login_required
def order_list(request):
    query = request.GET.get("q", "").strip()
    orders = Order.objects.select_related("customer").prefetch_related("materials__ingredient")
    if query:
        orders = orders.filter(
            Q(number__icontains=query) | Q(customer__name__icontains=query) | Q(product__icontains=query)
        )
    columns = [
        (status, Order.Status(status).label, orders.filter(status=status))
        for status in KANBAN_STATUSES
    ]
    stats = {
        "total": orders.count(),
        "production": orders.filter(
            status__in=[
                Order.Status.PREPARING,
                Order.Status.BAKED,
                Order.Status.QUALITY,
            ]
        ).count(),
        "ready": orders.filter(status=Order.Status.READY).count(),
    }
    return render(
        request,
        "pedidos/order_list.html",
        {"columns": columns, "query": query, "stats": stats},
    )


@role_required(SALES)
def order_create(request):
    order = Order(created_by=request.user)
    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        formset = MaterialFormSet(request.POST, instance=order, prefix="materials")
        if form.is_valid() and formset.is_valid():
            saved_order = form.save(commit=False)
            saved_order.created_by = request.user
            saved_order.save()
            formset.instance = saved_order
            formset.save()
            OrderStatusHistory.objects.create(
                order=saved_order, previous_status="", new_status=saved_order.status, changed_by=request.user
            )
            messages.success(request, f"Pedido {saved_order.number} creado. Revisa y envía la cotización.")
            return redirect("order_detail", pk=saved_order.pk)
    else:
        form = OrderForm(instance=order)
        formset = MaterialFormSet(instance=order, prefix="materials")
    return render(request, "pedidos/order_form.html", {"form": form, "formset": formset, "title": "Nuevo pedido"})


@role_required(SALES)
def order_edit(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if (
        order.inventory_reserved
        or order.status != Order.Status.RECEIVED
        or order.quote_status in (Order.QuoteStatus.SENT, Order.QuoteStatus.APPROVED)
    ):
        messages.error(request, "Solo se pueden editar pedidos recibidos antes de descontar inventario.")
        return redirect("order_detail", pk=order.pk)
    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        formset = MaterialFormSet(request.POST, instance=order, prefix="materials")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(pk=order.pk)

                if (
                    locked_order.inventory_reserved
                    or locked_order.status != Order.Status.RECEIVED
                    or locked_order.quote_status in (
                        Order.QuoteStatus.SENT,
                        Order.QuoteStatus.APPROVED,
                    )
                ):
                    messages.error(request, "El pedido cambió y ya no se puede editar.")
                    return redirect("order_detail", pk=order.pk)

                form.instance = locked_order
                new_price = form.cleaned_data.get("sale_price")
                total_paid = locked_order.total_paid

                if total_paid > 0 and (
                    new_price is None or new_price < total_paid
                ):
                    messages.error(
                        request,
                        f"El precio no puede ser inferior a los ${total_paid} ya abonados."
                    )
                    return redirect("order_detail", pk=locked_order.pk)

                updated_order = form.save()
                formset.instance = updated_order
                formset.save()

                if updated_order.quote_status == Order.QuoteStatus.REJECTED:
                    updated_order.quote_status = Order.QuoteStatus.DRAFT
                    updated_order.save(update_fields=["quote_status", "updated_at"])

                messages.success(request, "Pedido actualizado.")
                return redirect("order_detail", pk=order.pk)
    else:
        form = OrderForm(instance=order)
        formset = MaterialFormSet(instance=order, prefix="materials")
    return render(request, "pedidos/order_form.html", {"form": form, "formset": formset, "title": "Editar pedido"})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related("materials__ingredient", "history__changed_by"),
        pk=pk,
    )
    from .payment_forms import PaymentForm
    from .roles import has_role

    payment_form = PaymentForm()
    can_register_payment = has_role(request.user, SALES)
    payments = order.payments.select_related("created_by").all()

    next_status = None
    next_status_label = None
    if order.status in KANBAN_STATUSES:
        index = KANBAN_STATUSES.index(order.status)
        if index < len(KANBAN_STATUSES) - 1:
            next_status = KANBAN_STATUSES[index + 1]
            next_status_label = Order.Status(next_status).label
    return render(
        request,
        "pedidos/order_detail.html",
        {"order": order, "kanban_statuses": KANBAN_STATUSES, "next_status": next_status,
         "next_status_label": next_status_label,
         "payment_form": payment_form,
         "can_register_payment": can_register_payment,
         "payments": payments},
    )


@role_required(SALES)
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.inventory_reserved:
        messages.error(request, "Cancela el pedido para devolver automáticamente los insumos antes de eliminarlo.")
        return redirect("order_detail", pk=pk)
    if request.method == "POST":
        order.delete()
        messages.success(request, "Pedido eliminado.")
        return redirect("order_list")
    return render(request, "pedidos/confirm_delete.html", {"object": order, "title": "Eliminar pedido"})


@login_required
@require_POST
def order_transition(request, pk):
    new_status = request.POST.get("status")
    get_object_or_404(Order, pk=pk)
    if new_status == Order.Status.CANCELLED:
        if not has_role(request.user, SALES):
            raise PermissionDenied("Solo Ventas o Administración puede cancelar pedidos.")
    elif not has_role(request.user, KITCHEN):
        raise PermissionDenied("Solo Cocina o Administración puede avanzar la producción.")
    try:
        transition_order(pk, new_status, request.user)
    except (ValidationError, ValueError) as exc:
        message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, message)
    else:
        messages.success(request, "Estado del pedido actualizado.")
    return redirect("order_detail", pk=pk)


@role_required(SALES)
@require_POST
def order_quote(request, pk):
    action = request.POST.get("action")
    target_status = {
        "send": Order.QuoteStatus.SENT,
        "approve": Order.QuoteStatus.APPROVED,
        "reject": Order.QuoteStatus.REJECTED,
    }.get(action)
    if not target_status:
        messages.error(request, "La cotización no puede cambiar a ese estado.")
        return redirect("order_detail", pk=pk)
    try:
        order = transition_quote(pk, target_status)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"Cotización {order.get_quote_status_display().lower()}.")
    return redirect("order_detail", pk=pk)


def _catalog(request, *, model, form_class, title, form_template, redirect_name, pk=None):
    instance = get_object_or_404(model, pk=pk) if pk is not None else None
    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"{title} guardado correctamente.")
            return redirect(redirect_name)
    else:
        form = form_class(instance=instance)
    return render(request, form_template, {"form": form, "title": title})


@login_required
def customer_list(request):
    return render(request, "pedidos/customer_list.html", {"objects": Customer.objects.all()})


@role_required(SALES)
def customer_create(request):
    return _catalog(request, model=Customer, form_class=CustomerForm, title="Cliente",
                    form_template="pedidos/form_page.html", redirect_name="customer_list")


@role_required(SALES)
def customer_edit(request, pk):
    return _catalog(request, model=Customer, form_class=CustomerForm, title="Cliente",
                    form_template="pedidos/form_page.html", redirect_name="customer_list", pk=pk)


@role_required(SALES)
def customer_delete(request, pk):
    return _delete_catalog(request, Customer, pk, "customer_list")


@login_required
def ingredient_list(request):
    return render(
        request,
        "pedidos/ingredient_list.html",
        {
            "objects": Ingredient.objects.all(),
            "movements": InventoryMovement.objects.select_related("ingredient", "created_by", "order")[:30],
        },
    )


@login_required
def inventory_movement_list(request):
    movements = InventoryMovement.objects.select_related("ingredient", "created_by", "order")[:100]
    return render(request, "pedidos/movement_list.html", {"objects": movements})


@role_required(WAREHOUSE)
def inventory_movement_create(request):
    if request.method == "POST":
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            movement = form.cleaned_data
            from .services import register_inventory_movement

            try:
                register_inventory_movement(
                    ingredient_id=movement["ingredient"].pk,
                    direction=movement["direction"],
                    quantity=movement["quantity"],
                    note=movement["note"],
                    user=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(request, "Movimiento registrado y existencia actualizada.")
                return redirect("ingredient_list")
    else:
        form = InventoryMovementForm()
    return render(
        request,
        "pedidos/form_page.html",
        {"form": form, "title": "Registrar movimiento de inventario"},
    )


@role_required(WAREHOUSE)
def ingredient_create(request):
    return _catalog(request, model=Ingredient, form_class=IngredientForm, title="Insumo",
                    form_template="pedidos/form_page.html", redirect_name="ingredient_list")


@role_required(WAREHOUSE)
def ingredient_edit(request, pk):
    return _catalog(request, model=Ingredient, form_class=IngredientForm, title="Insumo",
                    form_template="pedidos/form_page.html", redirect_name="ingredient_list", pk=pk)


@role_required(WAREHOUSE)
def ingredient_delete(request, pk):
    return _delete_catalog(request, Ingredient, pk, "ingredient_list")


@login_required
def dispatch_list(request):
    dispatches = Dispatch.objects.select_related("order", "order__customer")
    return render(request, "pedidos/dispatch_list.html", {"objects": dispatches})


@role_required(DISPATCH_ROLE)
def dispatch_create(request):
    return _dispatch_form(request)


@role_required(DISPATCH_ROLE)
def dispatch_edit(request, pk):
    return _dispatch_form(request, pk)


def _dispatch_form(request, pk=None):
    instance = get_object_or_404(Dispatch, pk=pk) if pk else None
    if request.method == "POST":
        form = DispatchForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            dispatch = form.save()
            messages.success(request, "Despacho guardado correctamente.")
            return redirect("dispatch_list")
    else:
        form = DispatchForm(instance=instance)
    return render(
        request,
        "pedidos/form_page.html",
        {"form": form, "title": "Despacho", "signature_enabled": True},
    )


@role_required(DISPATCH_ROLE)
def dispatch_delete(request, pk):
    dispatch = get_object_or_404(Dispatch, pk=pk)
    if dispatch.status == Dispatch.Status.DELIVERED:
        messages.error(request, "No se puede eliminar un despacho entregado y su comprobante.")
        return redirect("dispatch_list")
    return _delete_catalog(request, Dispatch, pk, "dispatch_list")


def _delete_catalog(request, model, pk, redirect_name):
    instance = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        try:
            instance.delete()
        except ProtectedError:
            messages.error(request, "No se puede eliminar: el registro está asociado a pedidos existentes.")
            return redirect(redirect_name)
        messages.success(request, "Registro eliminado.")
        return redirect(redirect_name)
    return render(request, "pedidos/confirm_delete.html", {"object": instance, "title": "Eliminar registro"})
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from .forms import TrabajadorCreationForm


@login_required
def trabajador_create(request):
    # Solo los superusuarios pueden crear trabajadores.
    if not request.user.is_superuser:
        raise PermissionDenied(
            "Solo el administrador puede crear trabajadores."
        )

    if request.method == "POST":
        form = TrabajadorCreationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                trabajador = form.save(commit=False)
                trabajador.is_staff = True
                trabajador.is_superuser = False
                trabajador.save()

                grupo = Group.objects.get(
                    name=form.cleaned_data["role"]
                )
                trabajador.groups.add(grupo)

            messages.success(
                request,
                "Trabajador creado correctamente."
            )
            return redirect("trabajador_list")
    else:
        form = TrabajadorCreationForm()

    return render(
        request,
        "pedidos/trabajador_form.html",
        {
            "form": form,
            "title": "Crear trabajador",
        },
    )
@login_required
def trabajador_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied(
            "Solo el administrador puede ver los trabajadores."
        )

    User = get_user_model()

    trabajadores = (
        User.objects
        .filter(is_superuser=False)
        .prefetch_related("groups")
        .order_by("username")
    )

    return render(
        request,
        "pedidos/trabajador_list.html",
        {
            "trabajadores": trabajadores,
            "title": "Gestión de trabajadores",
        },
    )
