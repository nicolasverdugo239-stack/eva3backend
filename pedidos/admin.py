from django.contrib import admin

from .models import (
    Customer,
    Dispatch,
    Ingredient,
    InventoryMovement,
    Order,
    OrderIngredient,
    OrderStatusHistory,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "created_at")
    search_fields = ("name", "phone", "email")
    ordering = ("name",)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "stock", "unit", "minimum_stock", "unit_cost", "stock_alert")
    list_filter = ("unit",)
    search_fields = ("name",)
    readonly_fields = ("stock", "updated_at")
    list_display_links = ("name",)

    @admin.display(description="Alerta")
    def stock_alert(self, obj):
        return "Reponer" if obj.is_low_stock else "Disponible"


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "ingredient", "direction", "quantity", "stock_after", "source", "order", "created_by")
    list_filter = ("direction", "source", "created_at")
    search_fields = ("ingredient__name", "order__number", "note", "created_by__username")
    readonly_fields = (
        "ingredient",
        "direction",
        "quantity",
        "stock_after",
        "source",
        "order",
        "note",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderIngredientInline(admin.TabularInline):
    model = OrderIngredient
    extra = 0

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and not (obj and obj.inventory_reserved)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not (obj and obj.inventory_reserved)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.inventory_reserved)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "product", "delivery_at", "quote_status", "status", "inventory_reserved")
    list_filter = ("status", "quote_status", "delivery_at")
    search_fields = ("number", "customer__name", "product")
    readonly_fields = ("number", "inventory_reserved", "created_at", "updated_at")
    inlines = [OrderIngredientInline]

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if not change:
            OrderStatusHistory.objects.create(
                order=obj, previous_status="", new_status=obj.status, changed_by=request.user
            )

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, "status", "quote_status")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.inventory_reserved)


@admin.register(Dispatch)
class DispatchAdmin(admin.ModelAdmin):
    list_display = ("order", "driver", "route_order", "scheduled_at", "status", "delivered_at")
    list_filter = ("status", "scheduled_at")
    search_fields = ("order__number", "driver", "order__customer__name")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (
            obj and obj.status == Dispatch.Status.DELIVERED
        )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "previous_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    search_fields = ("order__number", "changed_by__username")
    readonly_fields = ("order", "previous_status", "new_status", "changed_by", "changed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderIngredient)
class OrderIngredientAdmin(admin.ModelAdmin):
    list_display = ("order", "ingredient", "quantity")
    list_filter = ("ingredient",)
    search_fields = ("order__number", "ingredient__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
