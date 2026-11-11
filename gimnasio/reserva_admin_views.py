"""Gestión de reservas desde el panel, con las mismas reglas de cupos."""

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Clase, Membresia, Reserva
from .servicios import promover_lista_espera


class ReservaAdministrativaForm(forms.Form):
    clase = forms.ModelChoiceField(queryset=Clase.objects.none(), label="Clase")
    socio = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(), label="Socio"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clase_actual = self.initial.get("clase")
        socio_actual = self.initial.get("socio")
        self.fields["clase"].queryset = Clase.objects.filter(
            Q(inicio__gt=timezone.now()) | Q(pk=clase_actual)
        ).order_by("inicio", "pk")
        self.fields["socio"].queryset = (
            get_user_model()
            .objects.filter(Q(is_staff=False, is_active=True) | Q(pk=socio_actual))
            .order_by("username")
        )
        self.fields["clase"].help_text = (
            "Para modificar la reserva, selecciona una clase futura."
        )
        self.fields["socio"].help_text = (
            "Selecciona un socio activo con membresía vigente."
        )

    def clean_socio(self):
        socio = self.cleaned_data["socio"]
        miembro = Membresia.objects.filter(socio=socio).first()
        if socio.is_staff or not miembro or not miembro.permite_acceso:
            raise forms.ValidationError("El socio debe tener una membresía vigente.")
        return socio


@staff_member_required
def reservas_admin(request):
    reservas = Reserva.objects.select_related("clase", "socio").order_by(
        "-clase__inicio", "creada", "pk"
    )
    return render(request, "gimnasio/reservas_admin.html", {"reservas": reservas})


@staff_member_required
def reserva_admin_crear(request):
    return _guardar(request)


@staff_member_required
def reserva_admin_editar(request, pk):
    return _guardar(request, pk)


def _guardar(request, pk=None):
    reserva = get_object_or_404(Reserva, pk=pk) if pk is not None else None
    version_inicial = (reserva.clase_id, reserva.socio_id) if reserva else None
    inicial = {"clase": reserva.clase_id, "socio": reserva.socio_id} if reserva else {}
    form = ReservaAdministrativaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        destino_id = form.cleaned_data["clase"].pk
        socio = form.cleaned_data["socio"]
        with transaction.atomic():
            clase_ids = {destino_id}
            if reserva:
                clase_ids.add(reserva.clase_id)
            clases = {
                clase.pk: clase
                for clase in Clase.objects.select_for_update()
                .filter(pk__in=clase_ids)
                .order_by("pk")
            }
            destino = clases.get(destino_id)
            if reserva:
                reserva = get_object_or_404(Reserva, pk=pk)
            duplicada = Reserva.objects.filter(clase_id=destino_id, socio=socio)
            if reserva:
                duplicada = duplicada.exclude(pk=reserva.pk)
            miembro = Membresia.objects.filter(socio=socio).first()
            if reserva and (reserva.clase_id, reserva.socio_id) != version_inicial:
                form.add_error(None, "La reserva cambió; vuelve a intentarlo.")
            elif not destino or destino.inicio <= timezone.now():
                form.add_error("clase", "La clase ya no está disponible.")
            elif not miembro or not miembro.permite_acceso:
                form.add_error("socio", "El socio debe tener una membresía vigente.")
            elif duplicada.exists():
                form.add_error(None, "Este socio ya tiene una reserva para la clase.")
            elif reserva and (reserva.clase_id, reserva.socio_id) == (
                destino_id,
                socio.pk,
            ):
                pass
            else:
                if reserva:
                    origen = clases.get(reserva.clase_id)
                    if not origen:
                        form.add_error(None, "La reserva cambió; vuelve a intentarlo.")
                    else:
                        reserva.clase = destino
                        reserva.socio = socio
                        reserva.espera = True
                        reserva.creada = timezone.now()
                        reserva.save(
                            update_fields=["clase", "socio", "espera", "creada"]
                        )
                        if origen.pk != destino.pk:
                            promover_lista_espera(origen)
                if not form.errors:
                    if not reserva:
                        Reserva.objects.create(clase=destino, socio=socio, espera=True)
                    promover_lista_espera(destino)
        if not form.errors:
            messages.success(request, "La reserva se guardó correctamente.")
            return redirect("reservas_admin")
    return render(
        request, "gimnasio/reserva_admin_form.html", {"form": form, "reserva": reserva}
    )


@staff_member_required
@require_POST
def reserva_admin_eliminar(request, pk):
    with transaction.atomic():
        reserva_inicial = get_object_or_404(Reserva, pk=pk)
        clase = get_object_or_404(
            Clase.objects.select_for_update(), pk=reserva_inicial.clase_id
        )
        reserva = get_object_or_404(Reserva, pk=pk, clase=clase)
        reserva.delete()
        promover_lista_espera(clase)
    messages.success(request, "La reserva se eliminó correctamente.")
    return redirect("reservas_admin")
