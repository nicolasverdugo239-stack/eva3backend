
from django.urls import path

from . import views
from . import notification_views

urlpatterns = [
    path("notificaciones/marcar-leida/", notification_views.mark_notification_read, name="mark_notification_read"),
    path("", views.dashboard, name="dashboard"),

    # PEDIDOS
    path("pedidos/", views.order_list, name="order_list"),
    path("pedidos/nuevo/", views.order_create, name="order_create"),
    path("pedidos/<int:pk>/", views.order_detail, name="order_detail"),
    path("pedidos/<int:pk>/editar/", views.order_edit, name="order_edit"),
    path("pedidos/<int:pk>/eliminar/", views.order_delete, name="order_delete"),
    path("pedidos/<int:pk>/estado/", views.order_transition, name="order_transition"),
    path("pedidos/<int:pk>/cotizacion/", views.order_quote, name="order_quote"),

    # CLIENTES
    path("clientes/", views.customer_list, name="customer_list"),
    path("clientes/nuevo/", views.customer_create, name="customer_create"),
    path("clientes/<int:pk>/editar/", views.customer_edit, name="customer_edit"),
    path("clientes/<int:pk>/eliminar/", views.customer_delete, name="customer_delete"),

    # INVENTARIO
    path("insumos/", views.ingredient_list, name="ingredient_list"),
    path("insumos/nuevo/", views.ingredient_create, name="ingredient_create"),
    path("insumos/<int:pk>/editar/", views.ingredient_edit, name="ingredient_edit"),
    path("insumos/<int:pk>/eliminar/", views.ingredient_delete, name="ingredient_delete"),

    # MOVIMIENTOS DE INVENTARIO
    path("inventario/movimientos/", views.inventory_movement_list, name="inventory_movement_list"),
    path("inventario/movimientos/nuevo/", views.inventory_movement_create, name="inventory_movement_create"),

    # DESPACHOS
    path("despachos/", views.dispatch_list, name="dispatch_list"),
    path("despachos/nuevo/", views.dispatch_create, name="dispatch_create"),
    path("despachos/<int:pk>/editar/", views.dispatch_edit, name="dispatch_edit"),
    path("despachos/<int:pk>/eliminar/", views.dispatch_delete, name="dispatch_delete"),

    # GESTIÓN DE TRABAJADORES
    path("trabajadores/", views.trabajador_list, name="trabajador_list"),
    path("trabajadores/nuevo/", views.trabajador_create, name="trabajador_create"),
]
