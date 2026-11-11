import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField("nombre", max_length=120)
    phone = models.CharField("teléfono", max_length=30)
    email = models.EmailField("correo", blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField("insumo", max_length=120, unique=True)
    unit = models.CharField("unidad", max_length=20, help_text="Ej.: kg, g, litro, unidad")
    stock = models.DecimalField(
        "existencia",
        max_digits=10,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    minimum_stock = models.DecimalField(
        "stock mínimo", max_digits=10, decimal_places=3, default=0, validators=[MinValueValidator(0)]
    )
    unit_cost = models.DecimalField(
        "costo por unidad", max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))]
    )
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "insumo"
        verbose_name_plural = "insumos"
        constraints = [
            models.CheckConstraint(condition=Q(stock__gte=0), name="ingredient_stock_nonnegative"),
            models.CheckConstraint(condition=Q(minimum_stock__gte=0), name="ingredient_minimum_nonnegative"),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="ingredient_cost_nonnegative"),
        ]

    @property
    def is_low_stock(self):
        return self.stock <= self.minimum_stock

    def __str__(self):
        return f"{self.name} ({self.unit})"


class InventoryMovement(models.Model):
    class Direction(models.TextChoices):
        IN = "IN", "Entrada"
        OUT = "OUT", "Salida"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Movimiento manual"
        PRODUCTION = "PRODUCTION", "Consumo de producción"
        CANCELLATION = "CANCELLATION", "Devolución por cancelación"

    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="movements", verbose_name="insumo"
    )
    direction = models.CharField("tipo", max_length=3, choices=Direction.choices)
    quantity = models.DecimalField(
        "cantidad", max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    stock_after = models.DecimalField("existencia resultante", max_digits=10, decimal_places=3)
    source = models.CharField("origen", max_length=12, choices=Source.choices, default=Source.MANUAL)
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
        verbose_name="pedido",
    )
    note = models.CharField("motivo / referencia", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="inventory_movements"
    )
    created_at = models.DateTimeField("registrado", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="movement_quantity_positive"),
            models.CheckConstraint(condition=Q(stock_after__gte=0), name="movement_stock_nonnegative"),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} · {self.ingredient.name} · {self.quantity}"


class Order(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recibido"
        PREPARING = "PREPARING", "En Preparación"
        BAKED = "BAKED", "Horneado/Decorado"
        QUALITY = "QUALITY", "Control de Calidad"
        READY = "READY", "Listo"
        CANCELLED = "CANCELLED", "Cancelado"

    class QuoteStatus(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        SENT = "SENT", "Enviada"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"

    number = models.CharField("número", max_length=24, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders", verbose_name="cliente")
    product = models.CharField("producto", max_length=120, help_text="Ej.: torta personalizada")
    design = models.TextField("diseño y personalización")
    delivery_at = models.DateTimeField("fecha y hora de entrega")
    delivery_address = models.CharField("dirección de entrega", max_length=255)
    notes = models.TextField("notas", blank=True)
    labor_cost = models.DecimalField(
        "mano de obra", max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))]
    )
    sale_price = models.DecimalField(
        "precio de venta acordado",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Precio final acordado con el cliente.",
    )

    quote_status = models.CharField(
        "estado de cotización", max_length=10, choices=QuoteStatus.choices, default=QuoteStatus.DRAFT
    )
    status = models.CharField("estado de producción", max_length=12, choices=Status.choices, default=Status.RECEIVED)
    inventory_reserved = models.BooleanField("insumos descontados", default=False, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders_created"
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["delivery_at", "-created_at"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"DA-{timezone.localdate():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_paid(self):
        from django.db.models import Sum

        return self.payments.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def balance_due(self):
        if self.sale_price is None:
            return None

        return max(
            self.sale_price - self.total_paid,
            Decimal("0.00"),
        )

    @property
    def payment_status(self):
        if self.sale_price is None:
            return "SIN_PRECIO"

        if self.total_paid == 0:
            return "PENDIENTE"

        if self.total_paid < self.sale_price:
            return "PARCIAL"

        return "PAGADO"

    @property
    def quote_total(self):
        return self.material_total + self.labor_cost

    @property
    def material_total(self):
        materials = sum(
            (line.quantity * line.ingredient.unit_cost for line in self.materials.select_related("ingredient").all()),
            start=0,
        )
        return materials

    @property
    def delivery_alert(self):
        from datetime import timedelta

        if self.status in (self.Status.READY, self.Status.CANCELLED):
            return "completed"

        now = timezone.now()

        if self.delivery_at < now:
            return "overdue"

        if self.delivery_at <= now + timedelta(hours=24):
            return "soon"

        return "on_time"

    @property
    def kanban_index(self):
        statuses = [self.Status.RECEIVED, self.Status.PREPARING, self.Status.BAKED, self.Status.QUALITY, self.Status.READY]
        return statuses.index(self.status) if self.status in statuses else -1

    def __str__(self):
        return f"{self.number} · {self.product}"


class OrderIngredient(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="materials", verbose_name="pedido")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="order_lines", verbose_name="insumo")
    quantity = models.DecimalField(
        "cantidad requerida", max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.UniqueConstraint(fields=["order", "ingredient"], name="unique_ingredient_per_order")
        ]
        verbose_name = "insumo de pedido"
        verbose_name_plural = "insumos del pedido"

    def __str__(self):
        return f"{self.ingredient}: {self.quantity} {self.ingredient.unit}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history", verbose_name="pedido")
    previous_status = models.CharField("estado anterior", max_length=12, choices=Order.Status.choices, blank=True)
    new_status = models.CharField("nuevo estado", max_length=12, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="order_status_changes"
    )
    changed_at = models.DateTimeField("fecha de cambio", auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "cambio de estado"
        verbose_name_plural = "historial de estados"


class Dispatch(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planificado"
        IN_ROUTE = "IN_ROUTE", "En ruta"
        DELIVERED = "DELIVERED", "Entregado"
        ISSUE = "ISSUE", "Incidencia"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="dispatch", verbose_name="pedido")
    driver = models.CharField("responsable de despacho", max_length=120)
    route_order = models.PositiveIntegerField("posición en ruta", default=1)
    scheduled_at = models.DateTimeField("hora programada")
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.PLANNED)
    proof_text = models.TextField("comprobante / firma digital", blank=True)
    proof_image = models.ImageField("fotografía de comprobante", upload_to="comprobantes/", blank=True)
    delivered_at = models.DateTimeField("entregado el", null=True, blank=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["scheduled_at", "route_order"]
        verbose_name = "despacho"
        verbose_name_plural = "despachos"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.pk:
            previous = Dispatch.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous == self.Status.DELIVERED and self.status != self.Status.DELIVERED:
                errors["status"] = "Una entrega confirmada no puede volver a un estado anterior."
        if self.order_id and self.order.status != Order.Status.READY:
            errors["order"] = "Solo se pueden despachar pedidos que estén listos."
        if self.status == self.Status.DELIVERED and not (self.proof_text.strip() or self.proof_image):
            errors["proof_text"] = "Registra una firma o comprobante antes de confirmar la entrega."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.status == self.Status.DELIVERED and not self.delivered_at:
            self.delivered_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Despacho {self.order.number} · {self.get_status_display()}"


class NotificationRead(models.Model):
    """Registra las alertas leídas por cada usuario."""

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="read_notifications",
    )

    notification_key = models.CharField(
        max_length=120,
    )

    read_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "notification_key"],
                name="unique_notification_read_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.notification_key}"


class Payment(models.Model):
    """Registro de pagos y abonos asociados a un pedido."""

    class Method(models.TextChoices):
        CASH = "CASH", "Efectivo"
        TRANSFER = "TRANSFER", "Transferencia"
        CARD = "CARD", "Tarjeta"

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="pedido",
    )

    amount = models.DecimalField(
        "monto abonado",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    method = models.CharField(
        "método de pago",
        max_length=10,
        choices=Method.choices,
    )

    reference = models.CharField(
        "referencia o comprobante",
        max_length=120,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments_registered",
        verbose_name="registrado por",
    )

    created_at = models.DateTimeField(
        "fecha del pago",
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Pago de ${self.amount} - {self.order.number}"
