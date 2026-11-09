from rest_framework.permissions import BasePermission, IsAuthenticated

from .roles import ADMINISTRATORS, DISPATCH, KITCHEN, SALES, WAREHOUSE


class RolePermission(BasePermission):
    message = "Tu cuenta no tiene el rol necesario para esta acción."
    permission_map = {}

    def has_permission(self, request, view):
        if not IsAuthenticated().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        required_roles = self.permission_map.get(getattr(view, "action", ""), ())
        if not required_roles:
            return request.method in ("GET", "HEAD", "OPTIONS")
        return request.user.groups.filter(name__in=(*required_roles, ADMINISTRATORS)).exists()


class SalesPermission(RolePermission):
    permission_map = {
        "create": (SALES,),
        "update": (SALES,),
        "partial_update": (SALES,),
        "destroy": (SALES,),
        "quote": (SALES,),
        "advance": (SALES,),
    }


class KitchenPermission(RolePermission):
    permission_map = {"advance": (KITCHEN,)}


class WarehousePermission(RolePermission):
    permission_map = {
        "create": (WAREHOUSE,),
        "update": (WAREHOUSE,),
        "partial_update": (WAREHOUSE,),
        "destroy": (WAREHOUSE,),
    }


class DispatchPermission(RolePermission):
    permission_map = {
        "create": (DISPATCH,),
        "update": (DISPATCH,),
        "partial_update": (DISPATCH,),
        "destroy": (DISPATCH,),
    }


class InventoryMovementPermission(RolePermission):
    permission_map = {"create": (WAREHOUSE,)}
