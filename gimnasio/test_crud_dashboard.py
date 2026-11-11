from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gimnasio.models import Clase, Membresia, Pago, Plan


class CrudDashboardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            username="administrador_prueba", password="clave", is_staff=True
        )
        cls.otro = get_user_model().objects.create_user(
            username="socio_existente", password="clave"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def guardar(self, recurso, datos, instancia=None):
        url = (
            reverse("editar", args=[recurso, instancia.pk])
            if instancia
            else reverse("crear", args=[recurso])
        )
        response = self.client.post(url, datos)
        self.assertEqual(
            response.status_code,
            302,
            getattr(response.context and response.context.get("form"), "errors", ""),
        )
        return response

    def test_crud_cinco_recursos_y_bloqueos(self):
        usuario = get_user_model()
        self.guardar(
            "socios",
            {
                "username": "socio_nuevo",
                "first_name": "Ana",
                "last_name": "Test",
                "email": "ana@example.org",
                "password": "UnaClaveLarga!27",
                "is_active": "on",
            },
        )
        socio = usuario.objects.get(username="socio_nuevo")
        self.assertTrue(socio.check_password("UnaClaveLarga!27"))
        self.guardar(
            "planes", {"nombre": "Mensual", "precio": "20000", "duracion_dias": "30"}
        )
        plan = Plan.objects.get(nombre="Mensual")
        hoy = timezone.localdate()
        datos_membresia = {
            "socio": socio.pk,
            "plan": plan.pk,
            "inicio": hoy.isoformat(),
            "fin": (hoy + timedelta(days=30)).isoformat(),
            "estado": "activa",
        }
        self.guardar("membresias", datos_membresia)
        miembro = Membresia.objects.get(socio=socio)
        self.guardar(
            "pagos",
            {
                "membresia": miembro.pk,
                "monto": "20000",
                "fecha": hoy.isoformat(),
                "detalle": "Primera cuota",
            },
        )
        pago = Pago.objects.get(membresia=miembro)
        fecha = timezone.localtime(timezone.now() + timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        self.guardar("clases", {"nombre": "Yoga", "inicio": fecha, "cupos": "10"})
        clase = Clase.objects.get(nombre="Yoga")

        recursos = [
            ("socios", socio),
            ("planes", plan),
            ("membresias", miembro),
            ("pagos", pago),
            ("clases", clase),
        ]
        for nombre, objeto in recursos:
            with self.subTest(recurso=nombre):
                self.assertEqual(
                    self.client.get(reverse("lista", args=[nombre])).status_code, 200
                )
                self.assertEqual(
                    self.client.get(
                        reverse("editar", args=[nombre, objeto.pk])
                    ).status_code,
                    200,
                )

        for nombre, contenido in [
            ("socios", "ana@example.org"),
            ("planes", "30 días"),
            ("membresias", "Activa"),
            ("pagos", "Primera cuota"),
            ("clases", "10 cupos"),
        ]:
            with self.subTest(detalle=nombre):
                self.assertContains(
                    self.client.get(reverse("lista", args=[nombre])), contenido
                )

        self.guardar(
            "socios",
            {
                "username": socio.username,
                "first_name": "Andrea",
                "last_name": "Test",
                "email": "ana@example.org",
                "password": "",
                "is_active": "on",
            },
            socio,
        )
        socio.refresh_from_db()
        self.assertEqual(socio.first_name, "Andrea")
        self.assertTrue(socio.check_password("UnaClaveLarga!27"))
        self.guardar(
            "planes",
            {"nombre": "Mensual Plus", "precio": "25000", "duracion_dias": "30"},
            plan,
        )
        datos_membresia["estado"] = "congelada"
        self.guardar("membresias", datos_membresia, miembro)
        self.guardar(
            "pagos",
            {
                "membresia": miembro.pk,
                "monto": "25000",
                "fecha": hoy.isoformat(),
                "detalle": "Actualizada",
            },
            pago,
        )
        self.guardar(
            "clases", {"nombre": "Yoga tarde", "inicio": fecha, "cupos": "11"}, clase
        )
        for obj, campo, valor in [
            (plan, "nombre", "Mensual Plus"),
            (miembro, "estado", "congelada"),
            (pago, "monto", 25000),
            (clase, "nombre", "Yoga tarde"),
        ]:
            obj.refresh_from_db()
            self.assertEqual(getattr(obj, campo), valor)

        self.client.post(reverse("eliminar", args=["planes", plan.pk]))
        self.assertTrue(Plan.objects.filter(pk=plan.pk).exists())
        for nombre, objeto in [
            ("pagos", pago),
            ("membresias", miembro),
            ("planes", plan),
            ("clases", clase),
            ("socios", socio),
        ]:
            self.assertEqual(
                self.client.post(
                    reverse("eliminar", args=[nombre, objeto.pk])
                ).status_code,
                302,
            )
            self.assertFalse(type(objeto).objects.filter(pk=objeto.pk).exists())

    def test_validaciones_y_permisos(self):
        hoy = timezone.localdate()
        invalidos = [
            ("socios", {"username": "inseguro", "password": "123", "is_active": "on"}),
            ("planes", {"nombre": "Plan", "precio": "-1", "duracion_dias": "0"}),
            ("clases", {"nombre": "Yoga", "inicio": "2030-01-01T10:00", "cupos": "0"}),
        ]
        for recurso, datos in invalidos:
            with self.subTest(recurso=recurso):
                response = self.client.post(reverse("crear", args=[recurso]), datos)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        plan = Plan.objects.create(nombre="Plan", precio=100, duracion_dias=30)
        response = self.client.post(
            reverse("crear", args=["membresias"]),
            {
                "socio": self.otro.pk,
                "plan": plan.pk,
                "inicio": hoy.isoformat(),
                "fin": (hoy - timedelta(days=1)).isoformat(),
                "estado": "activa",
            },
        )
        self.assertTrue(response.context["form"].errors)
        miembro = Membresia.objects.create(
            socio=self.otro, plan=plan, inicio=hoy, fin=hoy + timedelta(days=1)
        )
        response = self.client.post(
            reverse("crear", args=["pagos"]),
            {"membresia": miembro.pk, "monto": "-1", "fecha": hoy.isoformat()},
        )
        self.assertTrue(response.context["form"].errors)
        self.client.force_login(self.otro)
        for recurso in ["socios", "planes", "membresias", "pagos", "clases"]:
            for url in [
                reverse("lista", args=[recurso]),
                reverse("crear", args=[recurso]),
            ]:
                self.assertEqual(self.client.get(url).status_code, 302)
