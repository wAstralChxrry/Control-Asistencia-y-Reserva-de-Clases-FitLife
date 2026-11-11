"""Mide el registro simulado de QR dentro de transacciones revertidas."""

from statistics import mean
from time import perf_counter

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import RequestFactory

from gimnasio.models import Membresia
from gimnasio.views import acceso


class Command(BaseCommand):
    help = (
        "Mide la vista de acceso QR en milisegundos sin conservar los cambios. "
        "Ejemplo: python manage.py medir_acceso_qr --membresia 1 --muestras 20. "
        "No incluye red, navegador ni carga concurrente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--membresia", type=int, required=True, help="ID de una membresía existente"
        )
        parser.add_argument(
            "--muestras",
            type=int,
            default=20,
            help="Número de mediciones, entre 1 y 100",
        )
        parser.add_argument("--tipo", choices=("entrada", "salida"), default="entrada")

    def handle(self, *args, **options):
        muestras = options["muestras"]
        if not 1 <= muestras <= 100:
            raise CommandError("El número de muestras debe estar entre 1 y 100.")
        miembro = Membresia.objects.filter(pk=options["membresia"]).first()
        empleado = (
            get_user_model().objects.filter(is_staff=True, is_active=True).first()
        )
        if not miembro or not empleado:
            raise CommandError(
                "Se necesita una membresía y un administrador activo existentes."
            )

        tiempos = []
        fabrica = RequestFactory()
        for _ in range(muestras):
            request = fabrica.post(
                "/acceso/", {"codigo": str(miembro.codigo), "tipo": options["tipo"]}
            )
            request.user = empleado
            request.session = {}
            request._messages = FallbackStorage(request)
            with transaction.atomic():
                inicio = perf_counter()
                respuesta = acceso(request)
                tiempos.append((perf_counter() - inicio) * 1000)
                transaction.set_rollback(True)
            if respuesta.status_code != 302:
                raise CommandError("La vista de acceso no respondió como se esperaba.")

        self.stdout.write(
            f"Muestras: {muestras}. Mínimo: {min(tiempos):.2f} ms; "
            f"media: {mean(tiempos):.2f} ms; máximo: {max(tiempos):.2f} ms."
        )
        self.stdout.write(
            "Transacciones revertidas. No incluye red, navegador ni carga concurrente."
        )
