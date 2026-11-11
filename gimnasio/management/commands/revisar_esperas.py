"""Revisa automáticamente los cupos disponibles de clases futuras."""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

from gimnasio.models import Clase
from gimnasio.servicios import promover_lista_espera


class Command(BaseCommand):
    help = "Revisa las listas de espera cada 30 segundos; usa --una-vez para ejecutar una revisión."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true")
        parser.add_argument("--intervalo", type=int, default=30)

    def handle(self, *args, **options):
        intervalo = options["intervalo"]
        if intervalo < 1:
            raise CommandError("El intervalo debe ser de al menos un segundo.")
        while True:
            if not options["una_vez"]:
                close_old_connections()
            try:
                ids = list(
                    Clase.objects.filter(
                        inicio__gt=timezone.now(), reservas__espera=True
                    )
                    .values_list("pk", flat=True)
                    .distinct()
                )
                total = 0
                for clase_id in ids:
                    with transaction.atomic():
                        clase = (
                            Clase.objects.select_for_update()
                            .filter(pk=clase_id)
                            .first()
                        )
                        if clase:
                            total += promover_lista_espera(clase)
                self.stdout.write(f"Lista de espera revisada: {total} cupos asignados.")
            except Exception as exc:
                if options["una_vez"]:
                    raise CommandError(
                        f"No se pudo revisar la lista de espera: {exc}"
                    ) from exc
                self.stderr.write(f"No se pudo revisar la lista de espera: {exc}")
            if options["una_vez"]:
                return
            time.sleep(intervalo)
