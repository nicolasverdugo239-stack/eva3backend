from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from pedidos.api import (
    CustomerViewSet,
    DispatchViewSet,
    IngredientViewSet,
    InventoryMovementViewSet,
    OrderViewSet,
    OrderIngredientViewSet,
)

router = DefaultRouter()
router.register("clientes", CustomerViewSet)
router.register("insumos", IngredientViewSet)
router.register("pedidos", OrderViewSet)
router.register("materiales-pedido", OrderIngredientViewSet)
router.register("despachos", DispatchViewSet)
router.register("movimientos-inventario", InventoryMovementViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="pedidos/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include(router.urls)),
    path("", include("pedidos.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
