from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Clase, Membresia, Plan, Reserva


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeguridadPorRolesTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin_rol", password="AdminSeguro42!"
        )
        self.socio = User.objects.create_user("socio_rol", password="ClaveSegura42!")
        self.otro = User.objects.create_user("otro_rol", password="ClaveSegura42!")
        plan = Plan.objects.create(nombre="Plan", precio=10000, duracion_dias=30)
        hoy = timezone.localdate()
        for usuario in (self.socio, self.otro):
            Membresia.objects.create(
                socio=usuario, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        self.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=3
        )
        self.reserva_ajena = Reserva.objects.create(clase=self.clase, socio=self.otro)

    def test_admin_puede_acceder_a_cada_area_administrativa(self):
        self.client.force_login(self.admin)
        for nombre in ["socios", "planes", "pagos", "membresias", "clases"]:
            for url in (
                reverse("lista", args=[nombre]),
                reverse("crear", args=[nombre]),
            ):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
        for url in [
            reverse("inicio"),
            reverse("acceso"),
            reverse("aforo"),
            reverse("participantes_clase", args=[self.clase.pk]),
            "/admin/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_socio_y_anonimo_no_entran_a_administracion(self):
        for usuario in (None, self.socio):
            if usuario:
                self.client.force_login(usuario)
            else:
                self.client.logout()
            for recurso in ["socios", "planes", "pagos", "membresias", "clases"]:
                for url, metodo in [
                    (reverse("lista", args=[recurso]), "get"),
                    (reverse("crear", args=[recurso]), "post"),
                    (reverse("editar", args=[recurso, 1]), "post"),
                    (reverse("eliminar", args=[recurso, 1]), "post"),
                ]:
                    with self.subTest(usuario=usuario, url=url):
                        self.assertIn(
                            getattr(self.client, metodo)(url).status_code, (302, 403)
                        )
            for url in [
                reverse("acceso"),
                reverse("aforo"),
                reverse("participantes_clase", args=[self.clase.pk]),
                reverse("reservas_admin"),
                reverse("reserva_admin_crear"),
                "/admin/",
            ]:
                with self.subTest(usuario=usuario, url=url):
                    self.assertIn(self.client.get(url).status_code, (302, 403))
            for nombre in ("reserva_admin_editar", "reserva_admin_eliminar"):
                url = reverse(nombre, args=[self.reserva_ajena.pk])
                with self.subTest(usuario=usuario, url=url):
                    self.assertIn(self.client.post(url).status_code, (302, 403))

    def test_reservas_y_datos_ajenos_no_son_accesibles(self):
        self.client.force_login(self.socio)
        self.assertEqual(
            self.client.post(
                reverse("cancelar", args=[self.reserva_ajena.pk])
            ).status_code,
            404,
        )
        self.assertTrue(Reserva.objects.filter(pk=self.reserva_ajena.pk).exists())
        self.assertEqual(self.client.get(reverse("qr")).status_code, 200)
        response = self.client.get(reverse("inicio"))
        self.assertNotContains(response, self.otro.username)
        self.assertNotContains(response, str(self.otro.membresia.codigo))

    def test_perfil_solo_modifica_datos_propios_permitidos(self):
        self.client.force_login(self.socio)
        response = self.client.post(
            reverse("perfil"),
            {
                "first_name": "Nuevo",
                "last_name": "Apellido",
                "email": "socio@example.com",
                "is_staff": "on",
                "is_superuser": "on",
                "id": self.otro.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.socio.refresh_from_db()
        self.otro.refresh_from_db()
        self.assertEqual(self.socio.first_name, "Nuevo")
        self.assertFalse(self.socio.is_staff)
        self.assertFalse(self.socio.is_superuser)
        self.assertNotEqual(self.otro.first_name, "Nuevo")

    def test_cambio_de_contrasena_exige_contrasena_actual(self):
        self.client.force_login(self.socio)
        data = {
            "old_password": "Incorrecta42!",
            "new_password1": "OtraClaveSegura987!",
            "new_password2": "OtraClaveSegura987!",
        }
        self.assertEqual(
            self.client.post(reverse("cambiar_contrasena"), data).status_code, 200
        )
        self.socio.refresh_from_db()
        self.assertTrue(self.socio.check_password("ClaveSegura42!"))
        data["old_password"] = "ClaveSegura42!"
        self.assertEqual(
            self.client.post(reverse("cambiar_contrasena"), data).status_code, 302
        )
        self.socio.refresh_from_db()
        self.assertTrue(self.socio.check_password("OtraClaveSegura987!"))
        self.assertEqual(self.client.get(reverse("perfil")).status_code, 200)

    def test_admin_no_ejecuta_acciones_reservadas_al_socio(self):
        self.client.force_login(self.admin)
        for url in [reverse("perfil"), reverse("cambiar_contrasena"), reverse("qr")]:
            self.assertEqual(self.client.get(url).status_code, 403)
        for url in [
            reverse("reservar", args=[self.clase.pk]),
            reverse("cancelar", args=[self.reserva_ajena.pk]),
        ]:
            self.assertEqual(self.client.post(url).status_code, 403)

    def test_socio_reserva_y_cancela_su_propias_clases(self):
        self.client.force_login(self.socio)
        self.assertEqual(
            self.client.post(reverse("reservar", args=[self.clase.pk])).status_code, 302
        )
        reserva = Reserva.objects.get(clase=self.clase, socio=self.socio)
        self.assertEqual(
            self.client.post(reverse("cancelar", args=[reserva.pk])).status_code, 302
        )
        self.assertFalse(Reserva.objects.filter(pk=reserva.pk).exists())
