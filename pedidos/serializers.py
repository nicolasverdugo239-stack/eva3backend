from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    Customer,
    Dispatch,
    Ingredient,
    InventoryMovement,
    Order,
    OrderIngredient,
    OrderStatusHistory,
)
from .services import register_inventory_movement


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"
        read_only_fields = ("created_at",)


class IngredientSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ingredient
        fields = "__all__"
        read_only_fields = ("stock", "updated_at")


class OrderIngredientSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    unit = serializers.CharField(source="ingredient.unit", read_only=True)

    class Meta:
        model = OrderIngredient
        fields = ("id", "order", "ingredient", "ingredient_name", "unit", "quantity")

    def validate(self, attrs):
        order = attrs.get("order", getattr(self.instance, "order", None))
        if order and (
            order.inventory_reserved
            or order.status != Order.Status.RECEIVED
            or order.quote_status in (Order.QuoteStatus.SENT, Order.QuoteStatus.APPROVED)
        ):
            raise serializers.ValidationError(
                "La lista BOM solo se puede modificar antes de enviar o aprobar la cotización."
            )
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    materials = OrderIngredientSerializer(many=True, read_only=True)
    quote_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    material_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = (
            "number",
            "status",
            "quote_status",
            "inventory_reserved",
            "created_by",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        order = super().create(validated_data)
        OrderStatusHistory.objects.create(
            order=order, previous_status="", new_status=order.status, changed_by=self.context["request"].user
        )
        return order

    def validate(self, attrs):
        if self.instance and (
            self.instance.status != Order.Status.RECEIVED
            or self.instance.quote_status in (Order.QuoteStatus.SENT, Order.QuoteStatus.APPROVED)
        ):
            raise serializers.ValidationError(
                "Solo se pueden editar pedidos recibidos con cotización en borrador o rechazada."
            )
        return attrs

    def validate_delivery_at(self, value):
        from django.utils import timezone

        if value <= timezone.now():
            raise serializers.ValidationError("La fecha de entrega debe estar en el futuro.")
        return value


class DispatchSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = Dispatch
        fields = "__all__"
        read_only_fields = ("delivered_at", "updated_at")

    def validate(self, attrs):
        order = attrs.get("order", getattr(self.instance, "order", None))
        dispatch_status = attrs.get("status", getattr(self.instance, "status", Dispatch.Status.PLANNED))
        proof_text = attrs.get("proof_text", getattr(self.instance, "proof_text", ""))
        proof_image = attrs.get("proof_image", getattr(self.instance, "proof_image", None))
        if (
            self.instance
            and self.instance.status == Dispatch.Status.DELIVERED
            and dispatch_status != Dispatch.Status.DELIVERED
        ):
            raise serializers.ValidationError({"status": "Una entrega confirmada no puede volver a un estado anterior."})
        if order and order.status != Order.Status.READY:
            raise serializers.ValidationError({"order": "Solo se pueden despachar pedidos que estén listos."})
        if dispatch_status == Dispatch.Status.DELIVERED and not (proof_text.strip() or proof_image):
            raise serializers.ValidationError({"proof_text": "Registra una firma o comprobante antes de confirmar la entrega."})
        return attrs


class InventoryMovementSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    unit = serializers.CharField(source="ingredient.unit", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = (
            "id",
            "ingredient",
            "ingredient_name",
            "unit",
            "direction",
            "quantity",
            "stock_after",
            "source",
            "order",
            "note",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("stock_after", "source", "order", "created_by", "created_at")

    def create(self, validated_data):
        try:
            return register_inventory_movement(
                ingredient_id=validated_data["ingredient"].pk,
                direction=validated_data["direction"],
                quantity=validated_data["quantity"],
                note=validated_data.get("note", ""),
                user=self.context["request"].user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"detail": exc.messages}) from exc
