"""Operaciones compartidas para mantener los cupos de las clases."""

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import connection

from .models import Clase, Membresia, Reserva

MENSAJE_HORARIO = "Ya tienes una inscripción en otra clase a la misma hora."


def bloquear_socio(socio_id):
    """Serializa las inscripciones simultáneas de un mismo socio."""
    return get_user_model().objects.select_for_update().get(pk=socio_id)


def tiene_conflicto_horario(socio_id, inicio, excluir_reserva=None):
    reservas = Reserva.objects.filter(socio_id=socio_id, clase__inicio=inicio)
    if excluir_reserva is not None:
        reservas = reservas.exclude(pk=excluir_reserva)
    return reservas.exists()


def clase_tiene_conflictos(clase, inicio):
    """Comprueba cambios de horario mientras se mantienen bloqueados los socios."""
    socios = list(clase.reservas.order_by().values_list("socio_id", flat=True))
    list(
        get_user_model()
        .objects.select_for_update()
        .filter(pk__in=socios)
        .order_by("pk")
    )
    return (
        Reserva.objects.filter(socio_id__in=socios, clase__inicio=inicio)
        .exclude(clase=clase)
        .exists()
    )


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
        usuarios = get_user_model().objects
        if connection.features.has_select_for_update_skip_locked:
            usuarios = usuarios.select_for_update(skip_locked=True)
        else:
            usuarios = usuarios.select_for_update()
        socio = usuarios.filter(pk=reserva.socio_id).first()
        # Mantiene el orden de espera cuando otro proceso bloquea al socio.
        if not socio:
            break
        miembro = socios_con_membresia.get(reserva.socio_id)
        if (
            miembro
            and socio.is_active
            and miembro.vigente
            and not Reserva.objects.filter(
                socio_id=reserva.socio_id, clase__inicio=clase.inicio, espera=False
            )
            .exclude(pk=reserva.pk)
            .exists()
        ):
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
