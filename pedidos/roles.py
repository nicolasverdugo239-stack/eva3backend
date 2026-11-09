from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

SALES = "Ventas"
KITCHEN = "Cocina"
WAREHOUSE = "Bodega"
DISPATCH = "Despacho"
ADMINISTRATORS = "Administradores"


def has_role(user, *roles):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or user.groups.filter(name__in=roles).exists()
    )


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def guarded(request, *args, **kwargs):
            if not has_role(request.user, *roles, ADMINISTRATORS):
                raise PermissionDenied("Tu cuenta no tiene el rol necesario para esta acción.")
            return view_func(request, *args, **kwargs)

        return login_required(guarded)

    return decorator
