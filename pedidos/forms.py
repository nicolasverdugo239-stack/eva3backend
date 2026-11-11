
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    Customer,
    Dispatch,
    Ingredient,
    InventoryMovement,
    Order,
    OrderIngredient,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


# FORMULARIO DE CLIENTES
class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email"]


# FORMULARIO DE INGREDIENTES
class IngredientForm(StyledModelForm):
    class Meta:
        model = Ingredient
        fields = [
            "name",
            "unit",
            "minimum_stock",
            "unit_cost",
        ]


# FORMULARIO DE MOVIMIENTOS DE INVENTARIO
class InventoryMovementForm(StyledModelForm):
    class Meta:
        model = InventoryMovement
        fields = [
            "ingredient",
            "direction",
            "quantity",
            "note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["direction"].choices = [
            (
                InventoryMovement.Direction.IN,
                "Entrada (recepción / compra)",
            ),
            (
                InventoryMovement.Direction.OUT,
                "Salida (merma / ajuste)",
            ),
        ]


# FORMULARIO DE PEDIDOS
class OrderForm(StyledModelForm):
    class Meta:
        model = Order

        fields = [
            "customer",
            "product",
            "design",
            "delivery_at",
            "delivery_address",
            "notes",
            "labor_cost",
        ]

        widgets = {
            "delivery_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "design": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["delivery_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]

    def clean_delivery_at(self):
        from django.utils import timezone

        value = self.cleaned_data["delivery_at"]

        if value <= timezone.now():
            raise forms.ValidationError(
                "La fecha de entrega debe estar en el futuro."
            )

        return value


# FORMULARIO DE MATERIALES DEL PEDIDO
class OrderIngredientForm(StyledModelForm):
    class Meta:
        model = OrderIngredient

        fields = [
            "ingredient",
            "quantity",
        ]


MaterialFormSet = inlineformset_factory(
    Order,
    OrderIngredient,
    form=OrderIngredientForm,
    extra=3,
    can_delete=True,
)


# FORMULARIO DE DESPACHOS
class DispatchForm(StyledModelForm):
    class Meta:
        model = Dispatch

        fields = [
            "order",
            "driver",
            "route_order",
            "scheduled_at",
            "status",
            "proof_text",
            "proof_image",
        ]

        widgets = {
            "scheduled_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "proof_text": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["order"].queryset = Order.objects.filter(
            status=Order.Status.READY
        )

        self.fields["scheduled_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]


# FORMULARIO PARA CREAR TRABAJADORES
class TrabajadorCreationForm(UserCreationForm):

    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
    )

    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
    )

    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
    )

    ROLE_CHOICES = [
        ("Ventas", "Ventas"),
        ("Bodega", "Bodega"),
        ("Cocina", "Cocina"),
        ("Despacho", "Despacho"),
    ]

    role = forms.ChoiceField(
        label="Rol del trabajador",
        choices=ROLE_CHOICES,
    )

    class Meta(UserCreationForm.Meta):
        model = User

        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
