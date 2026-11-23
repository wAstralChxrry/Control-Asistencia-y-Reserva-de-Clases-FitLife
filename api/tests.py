from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from gimnasio.models import Clase, Membresia, Plan, Reserva


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ApiTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            "admin", password="clave-fuerte-123", is_staff=True
        )
        self.socio = User.objects.create_user("socio", password="clave-fuerte-123")
        self.otro = User.objects.create_user("otro", password="clave-fuerte-123")
        plan = Plan.objects.create(nombre="Bronce", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        for usuario in [self.socio, self.otro]:
            Membresia.objects.create(
                socio=usuario, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        self.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        self.client = APIClient()

    def test_jwt_y_permiso_administrador(self):
        self.assertEqual(self.client.get("/api/planes/").status_code, 401)
        response = self.client.post(
            "/api/token/",
            {"username": "socio", "password": "clave-fuerte-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        self.assertEqual(self.client.get("/api/planes/").status_code, 403)
        self.assertEqual(self.client.get("/api/clases/").status_code, 200)

    def test_crud_admin_y_validacion(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/planes/",
            {"nombre": "Oro", "precio": 200, "duracion_dias": 30},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        url = f"/api/planes/{response.data['id']}/"
        self.assertEqual(
            self.client.patch(url, {"precio": 300}, format="json").status_code, 200
        )
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(
            self.client.post(
                "/api/planes/",
                {"nombre": "Mal", "precio": -1, "duracion_dias": 0},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                "/api/clases/no-es-numero/", {"cupos": 1}, format="json"
            ).status_code,
            404,
        )

    def test_espera_y_privacidad(self):
        self.client.force_authenticate(self.socio)
        self.assertEqual(
            self.client.post(
                "/api/reservas/reservar/", {"clase": self.clase.pk}, format="json"
            ).status_code,
            201,
        )
        reserva = Reserva.objects.get(socio=self.socio)
        self.client.force_authenticate(self.otro)
        response = self.client.post(
            "/api/reservas/reservar/", {"clase": self.clase.pk}, format="json"
        )
        self.assertTrue(response.data["espera"])
        self.assertEqual(
            self.client.post(f"/api/reservas/{reserva.pk}/cancelar/").status_code, 404
        )
        self.client.force_authenticate(self.socio)
        self.assertEqual(
            self.client.post(f"/api/reservas/{reserva.pk}/cancelar/").status_code, 204
        )
        self.assertFalse(Reserva.objects.get(socio=self.otro).espera)

    def test_admin_reservas_y_control_de_acceso(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/reservas/",
            {"clase": self.clase.pk, "socio": self.socio.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        reserva_id = response.data["id"]
        response = self.client.patch(
            f"/api/reservas/{reserva_id}/", {"socio": self.otro.pk}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reserva.objects.get(pk=reserva_id).socio, self.otro)
        self.assertEqual(
            self.client.delete(f"/api/reservas/{reserva_id}/").status_code, 204
        )
        miembro = Membresia.objects.get(socio=self.socio)
        response = self.client.post(
            "/api/accesos/",
            {"codigo": str(miembro.codigo), "tipo": "entrada"},
            format="json",
        )
        self.assertTrue(response.data["permitido"])
        self.assertEqual(self.client.get("/api/aforo/").data["aforo"], 1)
        self.client.force_authenticate(self.socio)
        self.assertEqual(self.client.get("/api/aforo/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/reservas/",
                {"clase": self.clase.pk, "socio": self.otro.pk},
                format="json",
            ).status_code,
            403,
        )

    def test_perfil_y_membresia_propios(self):
        self.client.force_authenticate(self.socio)
        response = self.client.patch(
            "/api/mi-cuenta/", {"first_name": "Ana", "is_staff": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.socio.refresh_from_db()
        self.assertFalse(self.socio.is_staff)
        self.assertEqual(self.socio.first_name, "Ana")
        self.assertEqual(
            self.client.get("/api/mi-membresia/").data["socio"], self.socio.pk
        )

    def test_resumen_qr_y_cupos(self):
        self.client.force_authenticate(self.socio)
        self.assertEqual(self.client.get("/api/mi-qr/")["Content-Type"], "image/png")
        self.assertEqual(self.client.get("/api/clases/").data[0]["disponibles"], 1)
        self.assertEqual(self.client.get("/api/resumen/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/resumen/").data["socios"], 2)

    def test_clave_de_socio_insegura_se_rechaza(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/socios/", {"username": "nuevo", "password": "123"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_cambiar_contrasena_invalida_token_anterior(self):
        response = self.client.post(
            "/api/token/",
            {"username": "socio", "password": "clave-fuerte-123"},
            format="json",
        )
        access = response.data["access"]
        refresh = response.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
        response = self.client.post(
            "/api/mi-cuenta/contrasena/",
            {
                "old_password": "clave-fuerte-123",
                "new_password1": "Otra-clave-larga-975!",
                "new_password2": "Otra-clave-larga-975!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/mi-cuenta/").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/", {"refresh": refresh}, format="json"
            ).status_code,
            401,
        )
        response = self.client.post(
            "/api/token/",
            {"username": "socio", "password": "Otra-clave-larga-975!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_renovacion_usuario_eliminado_no_produce_error_500(self):
        response = self.client.post(
            "/api/token/",
            {"username": "otro", "password": "clave-fuerte-123"},
            format="json",
        )
        refresh = response.data["refresh"]
        self.otro.delete()
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/", {"refresh": refresh}, format="json"
            ).status_code,
            401,
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConcurrenciaReservasTest(TransactionTestCase):
    def test_dos_socios_no_sobrepasan_el_cupo(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connection

        if connection.vendor != "postgresql":
            self.skipTest("Requiere PostgreSQL para verificar bloqueos reales.")
        User = get_user_model()
        usuarios = [User.objects.create_user(f"concurrente{i}") for i in range(2)]
        plan = Plan.objects.create(nombre="Plan", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        for usuario in usuarios:
            Membresia.objects.create(
                socio=usuario, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        clase = Clase.objects.create(
            nombre="Spinning", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        barrera = Barrier(2, timeout=10)

        def reservar(usuario):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=usuario)
                barrera.wait()
                return cliente.post(
                    "/api/reservas/reservar/", {"clase": clase.pk}, format="json"
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(reservar, usuarios))
        self.assertEqual(resultados, [201, 201])
        self.assertEqual(Reserva.objects.filter(clase=clase, espera=False).count(), 1)
        self.assertEqual(Reserva.objects.filter(clase=clase, espera=True).count(), 1)
