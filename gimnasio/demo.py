"""Carga y retirada controlada de datos de demostración."""

from datetime import datetime, time, timedelta
import os
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Acceso, Clase, LoteDemo, Membresia, Pago, Plan, Reserva


class DemoConfiguracionError(Exception):
    """La contraseña de demostración no está configurada para este entorno."""


def clave_demo():
    if settings.DEBUG:
        return "admin123"
    clave = os.getenv("FITLIFE_DEMO_PASSWORD", "")
    if not clave or clave == "admin123":
        raise DemoConfiguracionError(
            "Configura FITLIFE_DEMO_PASSWORD con una contraseña segura antes de usar los datos de demostración."
        )
    try:
        validate_password(clave)
    except ValidationError as error:
        raise DemoConfiguracionError(
            "La contraseña FITLIFE_DEMO_PASSWORD no cumple los validadores configurados."
        ) from error
    return clave


def crear_lote_demo():
    with transaction.atomic():
        lote, creado = LoteDemo.objects.get_or_create(pk=1)
        if not creado:
            return False

        clave = clave_demo()

        planes = [
            Plan.objects.create(nombre="Bronce", precio=24990, duracion_dias=30),
            Plan.objects.create(nombre="Plata", precio=39990, duracion_dias=30),
            Plan.objects.create(nombre="Oro", precio=59990, duracion_dias=30),
        ]
        personas = [
            ("Camila", "Rojas"),
            ("Matías", "Soto"),
            ("Valentina", "Muñoz"),
            ("Benjamín", "Torres"),
            ("Fernanda", "Silva"),
            ("Diego", "Castro"),
            ("Antonia", "Vega"),
            ("Sebastián", "Pérez"),
        ]
        hoy = timezone.localdate()
        primer_dia = hoy + timedelta(days=1)
        usuarios, membresias, pagos, accesos = [], [], [], []
        for indice, (nombre, apellido) in enumerate(personas):
            usuario = get_user_model()(
                username=f"demo_{slugify(nombre)}_{slugify(apellido)}_{uuid4().hex[:4]}",
                first_name=nombre,
                last_name=apellido,
                email=f"demo{indice + 1}@example.invalid",
            )
            usuario.set_password(clave)
            usuario.save()
            usuarios.append(usuario)
            plan = planes[indice % len(planes)]
            miembro = Membresia.objects.create(
                socio=usuario,
                plan=plan,
                inicio=hoy - timedelta(days=10),
                fin=(
                    hoy + timedelta(days=20) if indice != 6 else hoy - timedelta(days=1)
                ),
                estado="congelada" if indice == 7 else "activa",
                dentro=indice < 3,
            )
            membresias.append(miembro)
            pagos.append(
                Pago.objects.create(
                    membresia=miembro,
                    monto=plan.precio,
                    fecha=hoy - timedelta(days=10),
                    detalle="Pago de demostración",
                )
            )
            if indice < 3:
                accesos.append(
                    Acceso.objects.create(
                        membresia=miembro,
                        tipo="entrada",
                        permitido=True,
                        detalle="Entrada de demostración",
                    )
                )

        clases = [
            Clase.objects.create(
                nombre=nombre,
                inicio=timezone.make_aware(
                    datetime.combine(primer_dia + timedelta(days=dias), time(horas, 0))
                ),
                cupos=cupos,
            )
            for nombre, dias, horas, cupos in [
                ("Spinning", 0, 18, 3),
                ("Yoga", 1, 9, 8),
                ("Entrenamiento funcional", 1, 18, 10),
                ("Pilates", 2, 10, 8),
            ]
        ]
        reservas = []
        for indice in range(5):
            reservas.append(
                Reserva.objects.create(
                    clase=clases[0],
                    socio=usuarios[indice],
                    espera=indice >= 3,
                )
            )
        for clase, indices in [
            (clases[1], [0, 2, 4]),
            (clases[2], [1, 3]),
            (clases[3], [5]),
        ]:
            for indice in indices:
                reservas.append(
                    Reserva.objects.create(clase=clase, socio=usuarios[indice])
                )
        lote.registros = {
            "usuarios": [u.pk for u in usuarios],
            "planes": [p.pk for p in planes],
            "membresias": [m.pk for m in membresias],
            "pagos": [p.pk for p in pagos],
            "accesos": [a.pk for a in accesos],
            "clases": [c.pk for c in clases],
            "reservas": [r.pk for r in reservas],
        }
        lote.save(update_fields=["registros"])
    return True


def borrar_lote_demo():
    with transaction.atomic():
        lote = LoteDemo.objects.select_for_update().filter(pk=1).first()
        if not lote:
            return "ausente"
        ids = lote.registros
        planes, usuarios = ids.get("planes", []), ids.get("usuarios", [])
        miembros, clases = ids.get("membresias", []), ids.get("clases", [])
        # No se elimina ninguna relación creada después de la carga inicial.
        externos = (
            Membresia.objects.filter(Q(plan_id__in=planes) | Q(socio_id__in=usuarios))
            .exclude(pk__in=miembros)
            .exists()
            or Pago.objects.filter(membresia_id__in=miembros)
            .exclude(pk__in=ids.get("pagos", []))
            .exists()
            or Reserva.objects.filter(Q(clase_id__in=clases) | Q(socio_id__in=usuarios))
            .exclude(clase_id__in=clases, socio_id__in=usuarios)
            .exists()
        )
        if externos:
            return "vinculados"
        Reserva.objects.filter(clase_id__in=clases, socio_id__in=usuarios).delete()
        Acceso.objects.filter(membresia_id__in=miembros).delete()
        Pago.objects.filter(
            pk__in=ids.get("pagos", []), membresia_id__in=miembros
        ).delete()
        Membresia.objects.filter(pk__in=miembros).delete()
        Clase.objects.filter(pk__in=clases).delete()
        Plan.objects.filter(pk__in=planes).delete()
        get_user_model().objects.filter(pk__in=usuarios, is_staff=False).delete()
        lote.delete()
    return "eliminado"


def generar_credenciales_demo():
    with transaction.atomic():
        lote = LoteDemo.objects.select_for_update().filter(pk=1).first()
        if not lote:
            return None, "ausente"
        usuario = (
            get_user_model()
            .objects.filter(
                pk__in=lote.registros.get("usuarios", []),
                is_staff=False,
                is_active=True,
                membresia__estado="activa",
                membresia__inicio__lte=timezone.localdate(),
                membresia__fin__gte=timezone.localdate(),
            )
            .order_by("pk")
            .first()
        )
        if not usuario:
            return None, "sin_socio"
        clave = clave_demo()
        usuario.set_password(clave)
        usuario.save(update_fields=["password"])
    return {"usuario": usuario.username, "contrasena": clave}, None


@staff_member_required
@require_POST
def cargar_demo(request):
    try:
        creado = crear_lote_demo()
    except DemoConfiguracionError as error:
        messages.error(request, str(error))
        return redirect("inicio")
    if creado:
        messages.success(request, "Datos de demostración cargados.")
    else:
        messages.info(request, "Los datos de demostración ya están cargados.")
    return redirect("inicio")


@staff_member_required
@require_POST
def eliminar_demo(request):
    resultado = borrar_lote_demo()
    if resultado == "ausente":
        messages.info(request, "No hay datos de demostración cargados.")
    elif resultado == "vinculados":
        messages.error(
            request,
            "No se pueden eliminar los datos de demostración: hay registros añadidos posteriormente vinculados a ellos.",
        )
    else:
        messages.success(request, "Datos de demostración eliminados.")
    return redirect("inicio")


@staff_member_required
@require_POST
def credenciales_demo(request):
    try:
        datos, error = generar_credenciales_demo()
    except DemoConfiguracionError as error:
        messages.error(request, str(error))
        return redirect("inicio")
    if error == "ausente":
        messages.error(request, "Primero carga los datos de demostración.")
    elif error == "sin_socio":
        messages.error(
            request, "No hay un socio de demostración con membresía vigente."
        )
    else:
        messages.success(
            request,
            f"Acceso de demostración: usuario {datos['usuario']} · contraseña {datos['contrasena']}.",
        )
    return redirect("inicio")
