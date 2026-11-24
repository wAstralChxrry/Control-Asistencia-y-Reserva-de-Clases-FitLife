from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.db import close_old_connections, connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from gimnasio.models import Clase, Membresia, Plan, Reserva
from gimnasio.servicios import promover_lista_espera


class ReservaHorarioTests(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.socio = usuario.objects.create_user("socio-horario", password="clave")
        self.admin = usuario.objects.create_user(
            "admin-horario", password="clave", is_staff=True
        )
        plan = Plan.objects.create(nombre="Plan", precio=100, duracion_meses=1)
        hoy = timezone.localdate()
        Membresia.objects.create(
            socio=self.socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        self.inicio = timezone.now() + timedelta(days=1)
        self.primera = Clase.objects.create(nombre="Yoga", inicio=self.inicio, cupos=2)
        self.segunda = Clase.objects.create(
            nombre="Spinning", inicio=self.inicio, cupos=2
        )
        self.client = APIClient()

    def test_socio_no_puede_inscribirse_a_dos_clases_a_la_misma_hora(self):
        self.client.force_authenticate(self.socio)
        self.assertEqual(
            self.client.post(
                "/api/reservas/reservar/", {"clase": self.primera.pk}, format="json"
            ).status_code,
            201,
        )
        respuesta = self.client.post(
            "/api/reservas/reservar/", {"clase": self.segunda.pk}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("misma hora", str(respuesta.data))
        self.assertEqual(Reserva.objects.filter(socio=self.socio).count(), 1)

    def test_admin_no_puede_inscribir_ni_reasignar_a_la_misma_hora(self):
        primera = Reserva.objects.create(clase=self.primera, socio=self.socio)
        otra = Clase.objects.create(
            nombre="Otra", inicio=self.inicio + timedelta(hours=2), cupos=1
        )
        segunda = Reserva.objects.create(clase=otra, socio=self.socio)
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(
                "/api/reservas/",
                {"socio": self.socio.pk, "clase": self.segunda.pk},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/reservas/{segunda.pk}/",
                {"clase": self.segunda.pk},
                format="json",
            ).status_code,
            400,
        )
        self.assertTrue(Reserva.objects.filter(pk=primera.pk).exists())

    def test_no_se_puede_mover_clase_a_hora_con_conflicto(self):
        otra = Clase.objects.create(
            nombre="Otra", inicio=self.inicio + timedelta(hours=2), cupos=1
        )
        Reserva.objects.create(clase=self.primera, socio=self.socio)
        Reserva.objects.create(clase=otra, socio=self.socio)
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/clases/{otra.pk}/",
            {"inicio": self.inicio.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_no_se_puede_cancelar_reserva_pasada(self):
        anterior = Clase.objects.create(
            nombre="Pasada", inicio=timezone.now() - timedelta(hours=1), cupos=1
        )
        reserva = Reserva.objects.create(clase=anterior, socio=self.socio)
        self.client.force_authenticate(self.socio)
        response = self.client.post(f"/api/reservas/{reserva.pk}/cancelar/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueos de PostgreSQL")
class ReservaHorarioConcurrenteTests(TransactionTestCase):
    def test_dos_clases_misma_hora_con_solicitudes_simultaneas(self):
        socio = get_user_model().objects.create_user(
            "socio-concurrente", password="clave"
        )
        plan = Plan.objects.create(nombre="Concurrente", precio=1, duracion_meses=1)
        hoy = timezone.localdate()
        Membresia.objects.create(
            socio=socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        inicio = timezone.now() + timedelta(days=1)
        clases = [
            Clase.objects.create(nombre=nombre, inicio=inicio, cupos=1)
            for nombre in ("Yoga", "Spinning")
        ]
        barrera = Barrier(2)

        def reservar(clase_id):
            close_old_connections()
            cliente = APIClient()
            cliente.force_authenticate(get_user_model().objects.get(pk=socio.pk))
            barrera.wait(timeout=10)
            try:
                return cliente.post(
                    "/api/reservas/reservar/", {"clase": clase_id}, format="json"
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            estados = list(ejecutor.map(reservar, [clase.pk for clase in clases]))
        self.assertCountEqual(estados, [201, 400])
        self.assertEqual(Reserva.objects.filter(socio=socio).count(), 1)

    def test_socio_nuevo_no_adelanta_a_persona_en_espera_bloqueada(self):
        usuario = get_user_model()
        primero = usuario.objects.create_user("primero-fifo", password="clave")
        segundo = usuario.objects.create_user("segundo-fifo", password="clave")
        plan = Plan.objects.create(nombre="FIFO", precio=1, duracion_meses=1)
        hoy = timezone.localdate()
        for socio in (primero, segundo):
            Membresia.objects.create(
                socio=socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        clase = Clase.objects.create(
            nombre="Yoga FIFO", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        reserva_primera = Reserva.objects.create(
            clase=clase, socio=primero, espera=True
        )
        bloqueado = Event()
        liberar = Event()

        def mantener_bloqueo():
            close_old_connections()
            try:
                with transaction.atomic():
                    usuario.objects.select_for_update().get(pk=primero.pk)
                    bloqueado.set()
                    if not liberar.wait(timeout=15):
                        raise TimeoutError("No se liberó el bloqueo de prueba")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            tarea = ejecutor.submit(mantener_bloqueo)
            try:
                self.assertTrue(bloqueado.wait(timeout=10))
                cliente = APIClient()
                cliente.force_authenticate(segundo)
                respuesta = cliente.post(
                    "/api/reservas/reservar/", {"clase": clase.pk}, format="json"
                )
                self.assertEqual(respuesta.status_code, 201)
                self.assertTrue(respuesta.data["espera"])
            finally:
                liberar.set()
                tarea.result(timeout=10)

        with transaction.atomic():
            clase = Clase.objects.select_for_update().get(pk=clase.pk)
            promover_lista_espera(clase)
        reserva_primera.refresh_from_db()
        self.assertFalse(reserva_primera.espera)
        self.assertTrue(Reserva.objects.get(clase=clase, socio=segundo).espera)
