from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Acceso, Clase, LoteDemo, Membresia, Pago, Plan, Reserva


class DemoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            "admin_demo_test", is_staff=True
        )
        cls.socio = get_user_model().objects.create_user("socio_real")
        cls.plan_real = Plan.objects.create(
            nombre="Real", precio=20000, duracion_dias=30
        )

    def test_carga_y_eliminacion_solo_afectan_lote(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cargar_demo"))
        self.client.post(reverse("cargar_demo"))
        self.assertEqual(LoteDemo.objects.count(), 1)
        self.assertEqual(Plan.objects.count(), 4)
        self.assertEqual(Membresia.objects.count(), 8)
        self.assertEqual(Clase.objects.count(), 4)
        self.assertEqual(Reserva.objects.filter(espera=True).count(), 2)
        self.assertEqual(Acceso.objects.filter(permitido=True).count(), 3)
        miembro = Membresia.objects.filter(dentro=False).first()
        self.client.post(
            reverse("acceso"), {"codigo": str(miembro.codigo), "tipo": "entrada"}
        )
        self.client.post(reverse("eliminar_demo"))
        self.assertFalse(LoteDemo.objects.exists())
        self.assertTrue(Plan.objects.filter(pk=self.plan_real.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.socio.pk).exists())
        self.assertFalse(Membresia.objects.exists())
        self.assertFalse(Clase.objects.exists())

    def test_no_borra_registros_externos_vinculados(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("cargar_demo"))
        miembro = Membresia.objects.first()
        pago = Pago.objects.create(
            membresia=miembro, monto=100, detalle="Registro posterior"
        )
        respuesta = self.client.post(reverse("eliminar_demo"), follow=True)
        self.assertContains(respuesta, "registros añadidos posteriormente")
        self.assertTrue(LoteDemo.objects.exists())
        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())

    def test_socio_no_puede_cargar_ni_eliminar(self):
        self.client.force_login(self.socio)
        self.client.post(reverse("cargar_demo"))
        self.assertFalse(LoteDemo.objects.exists())
        self.client.force_login(self.admin)
        self.client.post(reverse("cargar_demo"))
        self.client.force_login(self.socio)
        self.client.post(reverse("eliminar_demo"))
        self.assertTrue(LoteDemo.objects.exists())
