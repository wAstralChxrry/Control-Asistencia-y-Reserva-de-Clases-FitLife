from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Acceso, Clase, Membresia, Pago, Plan, Reserva


class ReservasAdministracionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            "administrador", password="ClaveSegura15!"
        )
        cls.socio = User.objects.create_user("socio1", password="ClaveSegura15!")
        cls.otro = User.objects.create_user("socio2", password="ClaveSegura15!")
        cls.tercero = User.objects.create_user("socio3", password="ClaveSegura15!")
        plan = Plan.objects.create(nombre="Mensual", precio=10000, duracion_dias=30)
        hoy = timezone.localdate()
        for socio in (cls.socio, cls.otro, cls.tercero):
            Membresia.objects.create(
                socio=socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        cls.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        cls.otra_clase = Clase.objects.create(
            nombre="Spinning", inicio=timezone.now() + timedelta(days=2), cupos=1
        )

    def test_admin_crea_ve_edita_y_elimina_reservas_con_promocion(self):
        self.client.force_login(self.admin)
        crear = reverse("reserva_admin_crear")
        ver = reverse("reservas_admin")
        self.assertEqual(
            self.client.post(
                crear, {"clase": self.clase.pk, "socio": self.socio.pk}
            ).status_code,
            302,
        )
        primera = Reserva.objects.get(socio=self.socio)
        self.assertFalse(primera.espera)
        self.client.post(crear, {"clase": self.clase.pk, "socio": self.otro.pk})
        segunda = Reserva.objects.get(socio=self.otro)
        self.assertTrue(segunda.espera)
        self.assertContains(self.client.get(ver), "socio2")
        self.assertEqual(
            self.client.get(
                reverse("reserva_admin_editar", args=[primera.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("reserva_admin_editar", args=[primera.pk]),
                {"clase": self.otra_clase.pk, "socio": self.socio.pk},
            ).status_code,
            302,
        )
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primera.clase_id, self.otra_clase.pk)
        self.assertFalse(segunda.espera)
        self.assertEqual(
            self.client.post(
                reverse("reserva_admin_eliminar", args=[primera.pk])
            ).status_code,
            302,
        )
        self.assertFalse(Reserva.objects.filter(pk=primera.pk).exists())

    def test_valida_membresia_y_reservas_duplicadas(self):
        self.client.force_login(self.admin)
        url = reverse("reserva_admin_crear")
        Reserva.objects.create(clase=self.clase, socio=self.socio)
        respuesta = self.client.post(
            url, {"clase": self.clase.pk, "socio": self.socio.pk}
        )
        self.assertContains(respuesta, "ya tiene una reserva")
        miembro = Membresia.objects.get(socio=self.otro)
        miembro.estado = "congelada"
        miembro.save()
        respuesta = self.client.post(
            url, {"clase": self.clase.pk, "socio": self.otro.pk}
        )
        self.assertContains(respuesta, "membresía vigente")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_socio_no_accede_a_gestion(self):
        reserva = Reserva.objects.create(clase=self.clase, socio=self.socio)
        self.client.force_login(self.socio)
        for name, args in (
            ("reservas_admin", []),
            ("reserva_admin_crear", []),
            ("reserva_admin_editar", [reserva.pk]),
        ):
            self.assertNotEqual(
                self.client.get(reverse(name, args=args)).status_code, 200
            )
        self.client.post(reverse("reserva_admin_eliminar", args=[reserva.pk]))
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())

    def test_editar_registro_pasado_con_socio_inactivo(self):
        self.clase.inicio = timezone.now() - timedelta(days=1)
        self.clase.save()
        self.socio.is_active = False
        self.socio.save()
        reserva = Reserva.objects.create(clase=self.clase, socio=self.socio)
        self.client.force_login(self.admin)
        url = reverse("reserva_admin_editar", args=[reserva.pk])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, self.clase.nombre)
        self.assertContains(respuesta, self.socio.username)
        respuesta = self.client.post(
            url, {"clase": self.clase.pk, "socio": self.socio.pk}
        )
        self.assertEqual(respuesta.status_code, 200)
        respuesta = self.client.post(
            url, {"clase": self.otra_clase.pk, "socio": self.otro.pk}
        )
        self.assertEqual(respuesta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(
            (reserva.clase_id, reserva.socio_id), (self.otra_clase.pk, self.otro.pk)
        )

    def test_admin_registra_y_ofrece_busqueda_y_filtros(self):
        self.client.force_login(self.admin)
        for model in (Plan, Pago, Membresia, Clase, Reserva, Acceso):
            self.assertIn(model, admin.site._registry)
            instancia = admin.site._registry[model]
            self.assertTrue(instancia.search_fields)
            self.assertTrue(instancia.list_filter)
            url = reverse(f"admin:gimnasio_{model._meta.model_name}_changelist")
            self.assertEqual(self.client.get(url, {"q": "socio"}).status_code, 200)
        self.client.force_login(self.socio)
        self.assertNotEqual(self.client.get(reverse("admin:index")).status_code, 200)
