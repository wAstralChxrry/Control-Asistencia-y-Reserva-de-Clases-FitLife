from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Clase, Membresia, Plan, Reserva


class PanelClasesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="personal", is_staff=True)
        cls.primero = User.objects.create_user(username="primero")
        cls.segundo = User.objects.create_user(username="segundo")
        cls.tercero = User.objects.create_user(username="tercero")
        plan = Plan.objects.create(nombre="Mensual", precio=100, duracion_dias=30)
        for usuario in (cls.primero, cls.segundo, cls.tercero):
            Membresia.objects.create(
                socio=usuario,
                plan=plan,
                inicio=timezone.localdate(),
                fin=timezone.localdate() + timedelta(days=30),
            )
        cls.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        Reserva.objects.create(clase=cls.clase, socio=cls.primero)
        Reserva.objects.create(clase=cls.clase, socio=cls.segundo, espera=True)
        Reserva.objects.create(clase=cls.clase, socio=cls.tercero, espera=True)

    def test_administrador_ve_participantes_y_espera(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("participantes_clase", args=[self.clase.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "primero")
        self.assertContains(response, "segundo")
        self.assertContains(response, "tercero")
        self.assertContains(response, "0 disponibles")
        self.assertLess(
            response.content.index(b"segundo"), response.content.index(b"tercero")
        )

    def test_socio_no_puede_ver_datos_de_otros_participantes(self):
        self.client.force_login(self.primero)
        response = self.client.get(reverse("participantes_clase", args=[self.clase.pk]))
        self.assertNotEqual(response.status_code, 200)
        self.assertNotContains(response, "segundo", status_code=response.status_code)

    def test_socio_ve_su_posicion_y_no_puede_volver_a_reservar(self):
        self.client.force_login(self.tercero)
        response = self.client.get(reverse("inicio"))
        self.assertContains(response, "posición 2")
        self.assertContains(response, "0 disponibles de 1 cupos")
        self.assertContains(response, "En espera")
        self.assertNotContains(response, "Unirse a espera")
        self.assertNotContains(response, "segundo")

    def test_socio_sin_reserva_ve_accion_de_espera(self):
        socio = User.objects.create_user(username="nuevo")
        self.client.force_login(socio)
        response = self.client.get(reverse("inicio"))
        self.assertContains(response, "Unirse a espera")

    def test_posicion_no_cuenta_socios_no_elegibles(self):
        self.segundo.is_active = False
        self.segundo.save(update_fields=["is_active"])
        self.client.force_login(self.tercero)
        response = self.client.get(reverse("inicio"))
        self.assertContains(response, "posición 1")

    def test_socio_en_espera_sin_vigencia_ve_aviso(self):
        membresia = Membresia.objects.get(socio=self.tercero)
        membresia.estado = "congelada"
        membresia.save(update_fields=["estado"])
        self.client.force_login(self.tercero)
        response = self.client.get(reverse("inicio"))
        self.assertContains(
            response, "necesitas una membresía vigente para recibir un cupo"
        )
