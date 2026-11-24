from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from gimnasio.models import Clase, Membresia, Plan, Reserva
from gimnasio.servicios import promover_lista_espera


class VigenciaParaClasesTests(TestCase):
    def setUp(self):
        usuarios = get_user_model()
        self.socio = usuarios.objects.create_user("socio-vigencia", password="clave")
        self.admin = usuarios.objects.create_user("admin-vigencia", is_staff=True)
        self.plan = Plan.objects.create(nombre="Mensual", precio=100, duracion_meses=1)
        hoy = timezone.localdate()
        self.miembro = Membresia.objects.create(
            socio=self.socio, plan=self.plan, inicio=hoy, fin=hoy + timedelta(days=1)
        )
        self.ultima = self.clase_en_fecha(hoy + timedelta(days=1), "Último día")
        self.posterior = self.clase_en_fecha(
            hoy + timedelta(days=2), "Fuera de vigencia"
        )
        self.api = APIClient()

    @staticmethod
    def clase_en_fecha(fecha, nombre):
        inicio = timezone.make_aware(datetime.combine(fecha, time(18)))
        return Clase.objects.create(nombre=nombre, inicio=inicio, cupos=2)

    def test_socio_puede_reservar_ultimo_dia_pero_no_despues(self):
        self.api.force_authenticate(self.socio)
        buena = self.api.post(
            "/api/reservas/reservar/", {"clase": self.ultima.pk}, format="json"
        )
        mala = self.api.post(
            "/api/reservas/reservar/", {"clase": self.posterior.pk}, format="json"
        )
        self.assertEqual(buena.status_code, 201)
        self.assertEqual(mala.status_code, 400)
        self.assertIn("fecha de la clase", str(mala.data))

    def test_admin_api_no_puede_inscribir_fuera_de_vigencia(self):
        self.api.force_authenticate(self.admin)
        respuesta = self.api.post(
            "/api/reservas/",
            {"clase": self.posterior.pk, "socio": self.socio.pk},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("fecha de la clase", str(respuesta.data))

    def test_espera_no_promueve_fuera_de_vigencia(self):
        reserva = Reserva.objects.create(
            clase=self.posterior, socio=self.socio, espera=True
        )
        with transaction.atomic():
            clase = Clase.objects.select_for_update().get(pk=self.posterior.pk)
            self.assertEqual(promover_lista_espera(clase), 0)
        reserva.refresh_from_db()
        self.assertTrue(reserva.espera)

    def test_reprogramar_clase_fuera_de_vigencia_se_rechaza(self):
        Reserva.objects.create(clase=self.ultima, socio=self.socio)
        self.api.force_authenticate(self.admin)
        respuesta = self.api.patch(
            f"/api/clases/{self.ultima.pk}/",
            {"inicio": self.posterior.inicio.isoformat()},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_panel_admin_bloquea_clase_fuera_de_vigencia(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("reserva_admin_crear"),
            {"socio": self.socio.pk, "clase": self.posterior.pk},
        )
        self.assertContains(respuesta, "fecha de la clase")
        self.assertFalse(Reserva.objects.filter(socio=self.socio).exists())

    def test_panel_admin_no_permite_dos_clases_a_misma_hora(self):
        Reserva.objects.create(clase=self.ultima, socio=self.socio)
        otra = Clase.objects.create(nombre="Otra", inicio=self.ultima.inicio, cupos=2)
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("reserva_admin_crear"), {"socio": self.socio.pk, "clase": otra.pk}
        )
        self.assertContains(respuesta, "misma hora")
        self.assertEqual(Reserva.objects.filter(socio=self.socio).count(), 1)
