from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Dispatch, Ingredient, InventoryMovement, Order, OrderIngredient


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email"]


class IngredientForm(StyledModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "minimum_stock", "unit_cost"]


class InventoryMovementForm(StyledModelForm):
    class Meta:
        model = InventoryMovement
        fields = ["ingredient", "direction", "quantity", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["direction"].choices = [
            (InventoryMovement.Direction.IN, "Entrada (recepción / compra)"),
            (InventoryMovement.Direction.OUT, "Salida (merma / ajuste)"),
        ]


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
            "delivery_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "design": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]

    def clean_delivery_at(self):
        from django.utils import timezone

        value = self.cleaned_data["delivery_at"]
        if value <= timezone.now():
            raise forms.ValidationError("La fecha de entrega debe estar en el futuro.")
        return value


class OrderIngredientForm(StyledModelForm):
    class Meta:
        model = OrderIngredient
        fields = ["ingredient", "quantity"]


MaterialFormSet = inlineformset_factory(
    Order, OrderIngredient, form=OrderIngredientForm, extra=3, can_delete=True
)


class DispatchForm(StyledModelForm):
    class Meta:
        model = Dispatch
        fields = ["order", "driver", "route_order", "scheduled_at", "status", "proof_text", "proof_image"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "proof_text": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].queryset = Order.objects.filter(status=Order.Status.READY)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
