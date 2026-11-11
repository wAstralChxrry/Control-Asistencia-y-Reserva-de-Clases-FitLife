from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Clase, LoteDemo, Membresia, Plan, Reserva


class AjustesDemoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            "admin_revision", is_staff=True
        )
        cls.socio = get_user_model().objects.create_user("socio_real")
        cls.plan = Plan.objects.create(nombre="Real", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        Membresia.objects.create(
            socio=cls.socio, plan=cls.plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        cls.clase = Clase.objects.create(
            nombre="Clase real", inicio=timezone.now() + timedelta(days=2), cupos=8
        )

    def test_reserva_reasignada_no_se_elimina_con_demo(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cargar_demo"))
        ids = LoteDemo.objects.get(pk=1).registros
        reserva = Reserva.objects.get(pk=ids["reservas"][0])
        reserva.socio = self.socio
        reserva.clase = self.clase
        reserva.save()
        self.client.post(reverse("eliminar_demo"))
        self.assertTrue(
            Reserva.objects.filter(
                pk=reserva.pk, socio=self.socio, clase=self.clase
            ).exists()
        )
        self.assertFalse(LoteDemo.objects.exists())

    def test_credenciales_solo_para_socio_demo(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cargar_demo"))
        resultado = self.client.post(reverse("credenciales_demo"), follow=True)
        self.assertContains(resultado, "Acceso de demostración")
        ids = LoteDemo.objects.get(pk=1).registros["usuarios"]
        self.assertTrue(
            all(
                u.check_password("admin123")
                for u in get_user_model().objects.filter(pk__in=ids)
            )
        )
        self.assertFalse(self.socio.has_usable_password())

    @override_settings(TIME_ZONE="America/Santiago", USE_TZ=True)
    def test_clase_texto_usa_hora_local(self):
        clase = Clase(
            nombre="Yoga",
            inicio=datetime(2026, 11, 12, 22, 0, tzinfo=dt_timezone.utc),
            cupos=5,
        )
        self.assertEqual(str(clase), "Yoga - 12/11/2026 19:00")

    def test_revision_periodica_asigna_cupo_a_membresia_que_comienza_hoy(self):
        socio = get_user_model().objects.create_user("espera_revision")
        hoy = timezone.localdate()
        Membresia.objects.create(
            socio=socio, plan=self.plan, inicio=hoy, fin=hoy + timedelta(days=10)
        )
        reserva = Reserva.objects.create(clase=self.clase, socio=socio, espera=True)
        call_command("revisar_esperas", una_vez=True, stdout=StringIO())
        reserva.refresh_from_db()
        self.assertFalse(reserva.espera)
