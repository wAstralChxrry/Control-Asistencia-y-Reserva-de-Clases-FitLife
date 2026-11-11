import uuid

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ClaseForm, MembresiaForm, PagoForm, PlanForm, SocioForm
from .models import Acceso, Clase, LoteDemo, Membresia, Pago, Plan, Reserva
from .permisos import solo_socio
from .servicios import promover_lista_espera, reconciliar_esperas

admin_required = user_passes_test(lambda u: u.is_active and u.is_staff)
RECURSOS = {
    "socios": (User, SocioForm),
    "planes": (Plan, PlanForm),
    "membresias": (Membresia, MembresiaForm),
    "pagos": (Pago, PagoForm),
    "clases": (Clase, ClaseForm),
}


@login_required
def inicio(request):
    if request.user.is_staff:
        return render(
            request,
            "gimnasio/dashboard.html",
            {
                "aforo": Membresia.objects.filter(dentro=True).count(),
                "socios": User.objects.filter(is_staff=False).count(),
                "clases": Clase.objects.filter(inicio__gte=timezone.now()).order_by(
                    "inicio"
                )[:5],
                "accesos": Acceso.objects.select_related("membresia__socio").order_by(
                    "-fecha"
                )[:8],
                "pagos": Pago.objects.count(),
                "demo_cargada": LoteDemo.objects.filter(pk=1).exists(),
            },
        )
    return render(
        request,
        "gimnasio/socio.html",
        {
            "membresia": Membresia.objects.filter(socio=request.user).first(),
            "clases": Clase.objects.filter(inicio__gt=timezone.now()).order_by(
                "inicio"
            ),
            "reservas": Reserva.objects.filter(socio=request.user).select_related(
                "clase"
            ),
        },
    )


@admin_required
def lista(request, recurso):
    model, _ = RECURSOS.get(recurso, (None, None))
    if not model:
        return HttpResponse(status=404)
    items = model.objects.all()
    if model is User:
        items = items.filter(is_staff=False)
    return render(request, "gimnasio/lista.html", {"items": items, "recurso": recurso})


@admin_required
def editar(request, recurso, pk=None):
    model, form_class = RECURSOS.get(recurso, (None, None))
    if not model:
        return HttpResponse(status=404)
    qs = model.objects.all()
    if model is User:
        qs = qs.filter(is_staff=False)
    instance = get_object_or_404(qs, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if model is Clase and instance:
                clase_bloqueada = Clase.objects.select_for_update().get(pk=instance.pk)
                if (
                    form.cleaned_data["cupos"]
                    < clase_bloqueada.reservas.filter(espera=False).count()
                ):
                    form.add_error(
                        "cupos",
                        "Los cupos no pueden ser menores que las reservas confirmadas.",
                    )
            if not form.errors:
                objeto = form.save()
                if model is Clase:
                    promover_lista_espera(objeto)
                elif model is Membresia:
                    reconciliar_esperas(objeto.socio_id)
                elif model is User:
                    reconciliar_esperas(objeto.pk)
        if not form.errors:
            messages.success(request, "Los datos se guardaron correctamente.")
            return redirect("lista", recurso=recurso)
    return render(request, "gimnasio/form.html", {"form": form, "recurso": recurso})


@admin_required
@require_POST
def eliminar(request, recurso, pk):
    model, _ = RECURSOS.get(recurso, (None, None))
    if not model:
        return HttpResponse(status=404)
    qs = model.objects.all()
    if model is User:
        qs = qs.filter(is_staff=False)
    obj = get_object_or_404(qs, pk=pk)
    try:
        obj.delete()
        messages.success(request, "El registro se eliminó correctamente.")
    except ProtectedError:
        messages.error(
            request, "No se puede eliminar porque tiene registros asociados."
        )
    return redirect("lista", recurso=recurso)


@admin_required
def acceso(request):
    if request.method == "POST":
        codigo, tipo = request.POST.get("codigo", "").strip(), request.POST.get("tipo")
        try:
            codigo = uuid.UUID(codigo)
        except ValueError:
            codigo = None
        with transaction.atomic():
            miembro = (
                Membresia.objects.select_for_update().filter(codigo=codigo).first()
                if codigo
                else None
            )
            if not miembro or tipo not in ("entrada", "salida"):
                messages.error(request, "Código o tipo de movimiento inválido.")
            else:
                permitido = (
                    (miembro.permite_acceso and not miembro.dentro)
                    if tipo == "entrada"
                    else miembro.dentro
                )
                detalle = (
                    "Movimiento registrado."
                    if permitido
                    else "Membresía no vigente o movimiento duplicado."
                )
                if permitido:
                    miembro.dentro = tipo == "entrada"
                    miembro.save(update_fields=["dentro"])
                Acceso.objects.create(
                    membresia=miembro, tipo=tipo, permitido=permitido, detalle=detalle
                )
                (messages.success if permitido else messages.error)(request, detalle)
        return redirect("acceso")
    return render(request, "gimnasio/acceso.html")


@solo_socio
def qr(request):
    miembro = get_object_or_404(Membresia, socio=request.user)
    response = HttpResponse(content_type="image/png")
    qrcode.make(str(miembro.codigo)).save(response, "PNG")
    return response


@admin_required
def aforo(request):
    return JsonResponse({"aforo": Membresia.objects.filter(dentro=True).count()})


@solo_socio
@require_POST
def reservar(request, pk):
    with transaction.atomic():
        clase = get_object_or_404(Clase.objects.select_for_update(), pk=pk)
        miembro = Membresia.objects.filter(socio=request.user).first()
        if not miembro or not miembro.permite_acceso or clase.inicio <= timezone.now():
            messages.error(
                request, "Necesitas una membresía vigente y una clase futura."
            )
        elif not Reserva.objects.filter(clase=clase, socio=request.user).exists():
            # Atiende primero a la lista de espera si hay plazas disponibles.
            promover_lista_espera(clase)
            espera = clase.reservas.filter(espera=False).count() >= clase.cupos
            Reserva.objects.create(clase=clase, socio=request.user, espera=espera)
            messages.success(
                request,
                "Inscripción en lista de espera." if espera else "Reserva confirmada.",
            )
        else:
            messages.info(request, "Ya tienes una inscripción para esta clase.")
    return redirect("inicio")


@solo_socio
@require_POST
def cancelar(request, pk):
    with transaction.atomic():
        clase_id = get_object_or_404(Reserva, pk=pk, socio=request.user).clase_id
        clase = Clase.objects.select_for_update().get(pk=clase_id)
        reserva = get_object_or_404(Reserva, pk=pk, socio=request.user, clase=clase)
        era_confirmada = not reserva.espera
        reserva.delete()
        if era_confirmada:
            promover_lista_espera(clase)
    return redirect("inicio")
