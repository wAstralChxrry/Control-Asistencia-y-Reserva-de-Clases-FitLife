from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from .models import Clase


@staff_member_required
def participantes_clase(request, pk):
    clase = get_object_or_404(Clase, pk=pk)
    reservas = clase.reservas.select_related("socio", "socio__membresia").order_by(
        "creada", "pk"
    )
    confirmadas = [reserva for reserva in reservas if not reserva.espera]
    espera = []
    posicion = 0
    for reserva in reservas:
        if not reserva.espera:
            continue
        membresia = getattr(reserva.socio, "membresia", None)
        elegible = bool(membresia and membresia.permite_acceso)
        if elegible:
            posicion += 1
        espera.append({"reserva": reserva, "posicion": posicion if elegible else None})
    return render(
        request,
        "gimnasio/participantes.html",
        {
            "clase": clase,
            "confirmadas": confirmadas,
            "espera": espera,
            "disponibles": max(0, clase.cupos - len(confirmadas)),
            "recurso": "clases",
        },
    )
