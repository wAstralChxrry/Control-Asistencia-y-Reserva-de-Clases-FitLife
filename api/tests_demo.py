from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from gimnasio.models import Clase, LoteDemo, Membresia, Pago, Plan, Reserva
from . import demo


@override_settings(
    DEBUG=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class DemoAPITest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = get_user_model().objects.create_user(
            "admin_api_demo", is_staff=True
        )
        self.socio = get_user_model().objects.create_user("socio_api_demo")

    def llamada(self, vista, user=None, method="post"):
        request = getattr(self.factory, method)("/api/demo/", {}, format="json")
        if user:
            force_authenticate(request, user=user)
        return vista(request)

    def test_controles_admin_y_limpieza(self):
        self.assertEqual(self.llamada(demo.cargar, self.socio).status_code, 403)
        self.assertFalse(LoteDemo.objects.exists())
        self.assertEqual(self.llamada(demo.cargar, self.admin).status_code, 201)
        self.assertEqual(self.llamada(demo.cargar, self.admin).status_code, 200)
        self.assertTrue(
            self.llamada(demo.estado, self.admin, method="get").data["cargada"]
        )
        lote = LoteDemo.objects.get(pk=1)
        self.assertEqual(
            Clase.objects.filter(
                pk__in=lote.registros["clases"], inicio__gt=timezone.now()
            ).count(),
            4,
        )
        credenciales = self.llamada(demo.acceso, self.admin)
        self.assertEqual(credenciales.status_code, 200)
        self.assertTrue(
            get_user_model()
            .objects.get(username=credenciales.data["usuario"])
            .check_password(credenciales.data["contrasena"])
        )
        self.assertIn("no-store", credenciales["Cache-Control"])
        self.assertEqual(self.llamada(demo.eliminar, self.admin).status_code, 200)
        self.assertFalse(LoteDemo.objects.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.socio.pk).exists())

    def test_rechaza_eliminar_registros_ajenos_vinculados(self):
        self.llamada(demo.cargar, self.admin)
        lote = LoteDemo.objects.get(pk=1)
        miembro = Membresia.objects.get(pk=lote.registros["membresias"][0])
        pago = Pago.objects.create(membresia=miembro, monto=200, detalle="posterior")
        respuesta = self.llamada(demo.eliminar, self.admin)
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(Pago.objects.filter(pk=pago.pk).exists())
        self.assertTrue(LoteDemo.objects.exists())

    def test_preserva_reserva_reasignada(self):
        plan = Plan.objects.create(nombre="Real", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        Membresia.objects.create(
            socio=self.socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
        )
        clase = Clase.objects.create(
            nombre="Real", inicio=timezone.now() + timedelta(days=2), cupos=5
        )
        self.llamada(demo.cargar, self.admin)
        reserva = Reserva.objects.get(
            pk=LoteDemo.objects.get(pk=1).registros["reservas"][0]
        )
        reserva.socio, reserva.clase = self.socio, clase
        reserva.save(update_fields=["socio", "clase"])
        self.assertEqual(self.llamada(demo.eliminar, self.admin).status_code, 200)
        self.assertTrue(
            Reserva.objects.filter(
                pk=reserva.pk, socio=self.socio, clase=clase
            ).exists()
        )

    @override_settings(DEBUG=False)
    def test_produccion_requiere_clave_segura_y_no_crea_datos(self):
        with patch.dict("os.environ", {"FITLIFE_DEMO_PASSWORD": ""}):
            self.assertEqual(self.llamada(demo.cargar, self.admin).status_code, 503)
        with patch.dict("os.environ", {"FITLIFE_DEMO_PASSWORD": "admin123"}):
            self.assertEqual(self.llamada(demo.cargar, self.admin).status_code, 503)
        self.assertFalse(LoteDemo.objects.exists())
        with patch.dict(
            "os.environ", {"FITLIFE_DEMO_PASSWORD": "FitLife2026#EjemploSeguro"}
        ):
            self.assertEqual(self.llamada(demo.cargar, self.admin).status_code, 201)
            credenciales = self.llamada(demo.acceso, self.admin)
            self.assertEqual(
                credenciales.data["contrasena"], "FitLife2026#EjemploSeguro"
            )
            self.assertIn("no-store", credenciales["Cache-Control"])
