"""Operaciones compartidas para mantener los cupos de las clases."""

from django.utils import timezone

from .models import Clase, Membresia, Reserva


def promover_lista_espera(clase):
    """Asigna plazas por orden a socios elegibles; conserva a los demás en espera.

    La persona que llama debe mantener el bloqueo de la fila de la clase hasta
    finalizar la transacción, igual que al crear o cancelar una reserva.
    """
    if clase.inicio <= timezone.now():
        return 0

    plazas = max(0, clase.cupos - clase.reservas.filter(espera=False).count())
    if not plazas:
        return 0

    socios_con_membresia = {
        miembro.socio_id: miembro
        for miembro in Membresia.objects.filter(
            socio_id__in=clase.reservas.filter(espera=True).values("socio_id")
        ).select_related("socio")
    }
    promovidos = 0
    for reserva in clase.reservas.filter(espera=True):
        miembro = socios_con_membresia.get(reserva.socio_id)
        if miembro and miembro.permite_acceso:
            reserva.espera = False
            reserva.save(update_fields=["espera"])
            promovidos += 1
            if promovidos == plazas:
                break
    return promovidos


def reconciliar_esperas(socio_id):
    """Revisa plazas tras cambiar la elegibilidad de un socio.

    Debe llamarse dentro de una transacción que incluya el cambio de socio o
    membresía. Los bloqueos se toman en orden estable para evitar interbloqueos.
    """
    clase_ids = list(
        Reserva.objects.filter(socio_id=socio_id, espera=True)
        .order_by("clase_id")
        .values_list("clase_id", flat=True)
        .distinct()
    )
    for clase in (
        Clase.objects.filter(pk__in=clase_ids).order_by("pk").select_for_update()
    ):
        promover_lista_espera(clase)
