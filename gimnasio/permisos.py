from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def solo_socio(view):
    """Restringe la vista a socios autenticados y activos."""

    @login_required
    @wraps(view)
    def comprobacion(request, *args, **kwargs):
        if not request.user.is_active or request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return comprobacion
