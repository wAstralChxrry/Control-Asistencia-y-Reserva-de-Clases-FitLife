from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Plan, Membresia, Clase, Reserva


class FlujosTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="clave", is_staff=True)
        self.socio = User.objects.create_user("socio", password="clave")
        self.otro = User.objects.create_user("otro", password="clave")
        plan = Plan.objects.create(nombre="Mensual", precio=20000, duracion_dias=30)
        hoy = timezone.localdate()
        self.miembro = Membresia.objects.create(
            socio=self.socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        Membresia.objects.create(
            socio=self.otro, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        self.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=1
        )

    def test_acceso_y_salida(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("acceso"), {"codigo": str(self.miembro.codigo), "tipo": "entrada"}
        )
        self.miembro.refresh_from_db()
        self.assertTrue(self.miembro.dentro)
        self.client.post(
            reverse("acceso"), {"codigo": str(self.miembro.codigo), "tipo": "salida"}
        )
        self.miembro.refresh_from_db()
        self.assertFalse(self.miembro.dentro)
        self.miembro.estado = "congelada"
        self.miembro.save()
        self.client.post(
            reverse("acceso"), {"codigo": str(self.miembro.codigo), "tipo": "entrada"}
        )
        self.miembro.refresh_from_db()
        self.assertFalse(self.miembro.dentro)

    def test_espera_y_promocion(self):
        self.client.force_login(self.socio)
        self.client.post(reverse("reservar", args=[self.clase.pk]))
        reserva = Reserva.objects.get(socio=self.socio)
        self.client.force_login(self.otro)
        self.client.post(reverse("reservar", args=[self.clase.pk]))
        self.assertTrue(Reserva.objects.get(socio=self.otro).espera)
        self.client.force_login(self.socio)
        self.client.post(reverse("cancelar", args=[reserva.pk]))
        self.assertFalse(Reserva.objects.get(socio=self.otro).espera)

    def test_socio_no_administra_ni_cancela_otra_reserva(self):
        reserva = Reserva.objects.create(socio=self.otro, clase=self.clase)
        self.client.force_login(self.socio)
        self.assertEqual(
            self.client.get(reverse("lista", args=["socios"])).status_code, 302
        )
        self.assertEqual(
            self.client.post(reverse("cancelar", args=[reserva.pk])).status_code, 404
        )

    def test_estado_vencido_se_muestra_correctamente(self):
        self.miembro.fin = timezone.localdate() - timedelta(days=1)
        self.miembro.save()
        self.assertEqual(self.miembro.estado_visible, "Vencida")
        self.assertFalse(self.miembro.vigente)

    def test_aumentar_cupos_promueve_lista_de_espera(self):
        Reserva.objects.create(socio=self.socio, clase=self.clase)
        espera = Reserva.objects.create(socio=self.otro, clase=self.clase, espera=True)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("editar", args=["clases", self.clase.pk]),
            {
                "nombre": self.clase.nombre,
                "inicio": timezone.localtime(self.clase.inicio).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "cupos": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        espera.refresh_from_db()
        self.assertFalse(espera.espera)

    def test_paginas_principales_responden(self):
        self.client.force_login(self.admin)
        for url in [
            reverse("inicio"),
            reverse("acceso"),
            reverse("lista", args=["socios"]),
            reverse("crear", args=["clases"]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.socio)
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)
        self.assertEqual(self.client.get(reverse("qr")).status_code, 200)
