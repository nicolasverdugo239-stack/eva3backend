from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.response import Response

from .models import Customer, Dispatch, Ingredient, InventoryMovement, Order, OrderIngredient
from .permissions import (
    DispatchPermission,
    InventoryMovementPermission,
    KitchenPermission,
    SalesPermission,
    WarehousePermission,
)
from .serializers import (
    CustomerSerializer,
    DispatchSerializer,
    IngredientSerializer,
    InventoryMovementSerializer,
    OrderIngredientSerializer,
    OrderSerializer,
)
from .services import transition_order, transition_quote


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [SalesPermission]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "No se puede eliminar un cliente que tenga pedidos asociados."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [WarehousePermission]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "No se puede eliminar un insumo usado por pedidos o movimientos de inventario."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related("customer").prefetch_related("materials__ingredient", "history")
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action == "advance":
            permission_class = (
                SalesPermission
                if self.request.data.get("status") == Order.Status.CANCELLED
                else KitchenPermission
            )
        else:
            permission_class = SalesPermission
        return [permission_class()]

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.inventory_reserved:
            return Response(
                {"detail": "Cancela el pedido para devolver los insumos antes de eliminarlo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get("status")
        if new_status not in Order.Status.values:
            raise APIValidationError({"status": "Indica un estado válido."})
        try:
            order = transition_order(order.pk, new_status, request.user)
        except ValidationError as exc:
            raise APIValidationError({"detail": exc.messages}) from exc
        return Response(self.get_serializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def quote(self, request, pk=None):
        order = self.get_object()
        quote_status = request.data.get("quote_status")
        if quote_status not in Order.QuoteStatus.values:
            raise APIValidationError({"quote_status": "Indica un estado válido."})
        try:
            order = transition_quote(order.pk, quote_status)
        except ValidationError as exc:
            raise APIValidationError({"quote_status": exc.messages}) from exc
        return Response(self.get_serializer(order).data)


class DispatchViewSet(viewsets.ModelViewSet):
    queryset = Dispatch.objects.select_related("order", "order__customer")
    serializer_class = DispatchSerializer
    permission_classes = [DispatchPermission]

    def destroy(self, request, *args, **kwargs):
        dispatch = self.get_object()
        if dispatch.status == Dispatch.Status.DELIVERED:
            return Response(
                {"detail": "No se puede eliminar un despacho entregado y su comprobante."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class OrderIngredientViewSet(viewsets.ModelViewSet):
    queryset = OrderIngredient.objects.select_related("order", "ingredient")
    serializer_class = OrderIngredientSerializer
    permission_classes = [SalesPermission]

    def perform_destroy(self, instance):
        if instance.order.inventory_reserved or instance.order.status != Order.Status.RECEIVED:
            raise APIValidationError("La lista BOM solo se puede modificar antes de iniciar la producción.")
        instance.delete()


class InventoryMovementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = InventoryMovement.objects.select_related("ingredient", "created_by", "order")
    serializer_class = InventoryMovementSerializer
    permission_classes = [InventoryMovementPermission]
