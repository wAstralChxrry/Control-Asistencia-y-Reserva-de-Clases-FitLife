from django import template
from django.db.models import Count, Q
from django.utils import timezone

from gimnasio.models import Clase, Reserva

register = template.Library()


@register.simple_tag
def informacion_clases(clases, usuario):
    """Añade disponibilidad y estado propio sin exponer datos de otros socios."""
    ids = [clase.pk for clase in clases]
    confirmadas = dict(
        Clase.objects.filter(pk__in=ids)
        .annotate(total=Count("reservas", filter=Q(reservas__espera=False)))
        .values_list("pk", "total")
    )
    propias = {
        reserva.clase_id: reserva
        for reserva in Reserva.objects.filter(clase_id__in=ids, socio=usuario)
    }
    resultado = []
    for clase in clases:
        disponibles = max(0, clase.cupos - confirmadas.get(clase.pk, 0))
        resultado.append(
            {
                "clase": clase,
                "disponibles": disponibles,
                "reserva": propias.get(clase.pk),
            }
        )
    return resultado


@register.simple_tag
def posiciones_espera(reservas):
    """Cuenta solo socios elegibles, en el orden de su inscripción."""
    reservas = list(reservas)
    ids = [reserva.clase_id for reserva in reservas if reserva.espera]
    posiciones = {}
    totales = {}
    for clase_id, reserva_id in (
        Reserva.objects.filter(
            clase_id__in=ids,
            espera=True,
            socio__is_active=True,
            socio__membresia__estado="activa",
            socio__membresia__inicio__lte=timezone.localdate(),
            socio__membresia__fin__gte=timezone.localdate(),
        )
        .order_by("clase_id", "creada", "pk")
        .values_list("clase_id", "pk")
    ):
        totales[clase_id] = totales.get(clase_id, 0) + 1
        posiciones[reserva_id] = totales[clase_id]
    return [
        {"reserva": reserva, "posicion": posiciones.get(reserva.pk)}
        for reserva in reservas
    ]
