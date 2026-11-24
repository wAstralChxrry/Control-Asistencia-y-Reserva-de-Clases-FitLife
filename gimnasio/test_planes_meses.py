from datetime import date
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from .fechas import fecha_fin_membresia
from .forms import MembresiaForm, PlanForm
from .models import Membresia, Plan


class CalculoMesesTest(SimpleTestCase):
    def test_calendario_con_meses_cortos_bisiestos_y_cambio_de_ano(self):
        casos = [
            (date(2027, 1, 31), 1, date(2027, 2, 27)),
            (date(2028, 1, 31), 1, date(2028, 2, 28)),
            (date(2027, 12, 15), 3, date(2028, 3, 14)),
            (date(2028, 2, 29), 12, date(2029, 2, 27)),
        ]
        for inicio, meses, fin in casos:
            with self.subTest(inicio=inicio, meses=meses):
                self.assertEqual(fecha_fin_membresia(inicio, meses), fin)


class MembresiaMesesTest(TestCase):
    def setUp(self):
        self.socio = get_user_model().objects.create_user(username="socio-meses")
        self.admin = get_user_model().objects.create_user(
            username="admin-meses", is_staff=True
        )
        self.plan = Plan.objects.create(
            nombre="Trimestral", precio=100, duracion_meses=3
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_api_calcula_fin_si_se_omite(self):
        respuesta = self.client.post(
            "/api/membresias/",
            {
                "socio": self.socio.pk,
                "plan": self.plan.pk,
                "inicio": "2027-12-15",
                "estado": "activa",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["fin"], "2028-03-14")

    def test_fecha_explicita_y_fecha_existente_se_respetan(self):
        respuesta = self.client.post(
            "/api/membresias/",
            {
                "socio": self.socio.pk,
                "plan": self.plan.pk,
                "inicio": "2027-12-15",
                "fin": "2028-03-20",
                "estado": "activa",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        pk = respuesta.data["id"]
        cambio = self.client.patch(
            f"/api/membresias/{pk}/", {"estado": "congelada"}, format="json"
        )
        self.assertEqual(cambio.status_code, 200, cambio.data)
        self.assertEqual(Membresia.objects.get(pk=pk).fin, date(2028, 3, 20))

    def test_formulario_calcula_fecha_omitada(self):
        formulario = MembresiaForm(
            {
                "socio": self.socio.pk,
                "plan": self.plan.pk,
                "inicio": "2027-12-15",
                "fin": "",
                "estado": "activa",
            }
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.save().fin, date(2028, 3, 14))

    def test_fechas_fuera_de_rango_no_producen_error_servidor(self):
        datos = {
            "socio": self.socio.pk,
            "plan": self.plan.pk,
            "inicio": "9999-12-31",
            "estado": "activa",
        }
        respuesta = self.client.post("/api/membresias/", datos, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("inicio", respuesta.data)
        formulario = MembresiaForm(datos)
        self.assertFalse(formulario.is_valid())
        self.assertIn("inicio", formulario.errors)

    def test_duracion_tiene_limite_en_formulario_y_api(self):
        datos = {"nombre": "Excesivo", "precio": 100, "duracion_meses": 1201}
        self.assertFalse(PlanForm(datos).is_valid())
        self.assertEqual(
            self.client.post("/api/planes/", datos, format="json").status_code, 400
        )


class ConversionPlanesTest(TestCase):
    def test_convierte_y_restaura_planes_de_30_60_y_90_dias(self):
        planes = [
            Plan.objects.create(nombre=str(dias), precio=100, duracion_meses=dias)
            for dias in (30, 60, 90)
        ]
        migracion = import_module("gimnasio.migrations.0004_plan_duracion_meses")
        editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        migracion.convertir_a_meses(apps, editor)
        self.assertEqual(
            list(
                Plan.objects.filter(pk__in=[p.pk for p in planes])
                .order_by("pk")
                .values_list("duracion_meses", flat=True)
            ),
            [1, 2, 3],
        )
        migracion.convertir_a_dias(apps, editor)
        self.assertEqual(
            list(
                Plan.objects.filter(pk__in=[p.pk for p in planes])
                .order_by("pk")
                .values_list("duracion_meses", flat=True)
            ),
            [30, 60, 90],
        )

    def test_rechaza_dias_no_equivalentes_sin_conversion_parcial(self):
        valido = Plan.objects.create(nombre="Mensual", precio=100, duracion_meses=30)
        invalido = Plan.objects.create(nombre="Especial", precio=100, duracion_meses=45)
        migracion = import_module("gimnasio.migrations.0004_plan_duracion_meses")
        with self.assertRaisesMessage(ValueError, str(invalido.pk)):
            migracion.convertir_a_meses(
                apps, SimpleNamespace(connection=SimpleNamespace(alias="default"))
            )
        valido.refresh_from_db()
        self.assertEqual(valido.duracion_meses, 30)
