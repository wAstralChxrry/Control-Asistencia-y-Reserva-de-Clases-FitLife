from datetime import timedelta
from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Acceso, Clase, Membresia, Plan, Reserva


class ReglasSegurasTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            "admin", "admin@example.com", "ClaveSegura1!"
        )
        self.socios = [
            User.objects.create_user(f"socio{i}", password="ClaveSegura1!")
            for i in range(3)
        ]
        plan = Plan.objects.create(nombre="Plan", precio=10000, duracion_dias=30)
        hoy = timezone.localdate()
        self.miembros = [
            Membresia.objects.create(
                socio=socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
            for socio in self.socios
        ]
        self.clase = Clase.objects.create(
            nombre="Yoga", inicio=timezone.now() + timedelta(days=1), cupos=1
        )
        self.client.force_login(self.admin)

    def test_socio_inactivo_no_puede_entrar_pero_puede_salir(self):
        socio = self.socios[0]
        socio.is_active = False
        socio.save()
        miembro = self.miembros[0]
        self.client.post(
            reverse("acceso"), {"codigo": miembro.codigo, "tipo": "entrada"}
        )
        miembro.refresh_from_db()
        self.assertFalse(miembro.dentro)
        self.assertFalse(Acceso.objects.latest("pk").permitido)
        miembro.dentro = True
        miembro.save(update_fields=["dentro"])
        self.client.post(
            reverse("acceso"), {"codigo": miembro.codigo, "tipo": "salida"}
        )
        miembro.refresh_from_db()
        self.assertFalse(miembro.dentro)
        self.assertTrue(Acceso.objects.latest("pk").permitido)

    def test_promocion_salta_inactivos_y_conserva_orden(self):
        primera = Reserva.objects.create(clase=self.clase, socio=self.socios[0])
        espera_inactiva = Reserva.objects.create(
            clase=self.clase, socio=self.socios[1], espera=True
        )
        espera_activa = Reserva.objects.create(
            clase=self.clase, socio=self.socios[2], espera=True
        )
        self.socios[1].is_active = False
        self.socios[1].save()
        self.client.force_login(self.socios[0])
        self.client.post(reverse("cancelar", args=[primera.pk]))
        espera_inactiva.refresh_from_db()
        espera_activa.refresh_from_db()
        self.assertTrue(espera_inactiva.espera)
        self.assertFalse(espera_activa.espera)

    def test_admin_reservas_y_accesos_son_solo_lectura(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        for model in (Reserva, Acceso):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
        self.assertIn(
            "dentro", admin.site._registry[Membresia].get_readonly_fields(request)
        )

    def test_medicion_qr_revierte_todas_las_escrituras(self):
        salida = StringIO()
        call_command(
            "medir_acceso_qr", membresia=self.miembros[0].pk, muestras=2, stdout=salida
        )
        self.miembros[0].refresh_from_db()
        self.assertFalse(self.miembros[0].dentro)
        self.assertFalse(Acceso.objects.exists())
        self.assertIn("Muestras: 2", salida.getvalue())

    def test_filtro_admin_incluye_vencidas_por_fecha(self):
        miembro = self.miembros[0]
        miembro.fin = timezone.localdate() - timedelta(days=1)
        miembro.save()
        response = self.client.get(
            reverse("admin:gimnasio_membresia_changelist"),
            {"estado_efectivo": "vencida"},
        )
        self.assertContains(response, self.socios[0].username)
        self.assertNotContains(response, self.socios[1].username)

    def test_reactivar_membresia_desde_dashboard_asigna_plaza_disponible(self):
        miembro = self.miembros[0]
        miembro.estado = "congelada"
        miembro.save()
        espera = Reserva.objects.create(
            clase=self.clase, socio=self.socios[0], espera=True
        )
        respuesta = self.client.post(
            reverse("editar", args=["membresias", miembro.pk]),
            {
                "socio": self.socios[0].pk,
                "plan": miembro.plan_id,
                "inicio": miembro.inicio.isoformat(),
                "fin": miembro.fin.isoformat(),
                "estado": "activa",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        espera.refresh_from_db()
        self.assertFalse(espera.espera)

    def test_reactivar_socio_desde_admin_asigna_plaza_disponible(self):
        from django.db import transaction

        socio = self.socios[0]
        socio.is_active = False
        socio.save()
        espera = Reserva.objects.create(clase=self.clase, socio=socio, espera=True)
        socio.is_active = True
        request = RequestFactory().post("/admin/auth/user/")
        request.user = self.admin
        with transaction.atomic():
            admin.site._registry[type(socio)].save_model(request, socio, None, True)
        espera.refresh_from_db()
        self.assertFalse(espera.espera)

    def test_admin_membresia_filtra_socios_y_valida_fechas(self):
        from datetime import date

        request = RequestFactory().get("/admin/")
        request.user = self.admin
        model_admin = admin.site._registry[Membresia]
        alta = model_admin.get_form(request)()
        self.assertNotIn(self.admin, alta.fields["socio"].queryset)
        nuevo = get_user_model().objects.create_user("nuevo")
        datos = {
            "socio": nuevo.pk,
            "plan": self.miembros[0].plan_id,
            "inicio": date(2027, 2, 1),
            "fin": date(2027, 1, 1),
            "estado": "activa",
        }
        alta_invalida = model_admin.get_form(request)(datos)
        self.assertFalse(alta_invalida.is_valid())
        self.assertIn("fecha final", str(alta_invalida.errors).lower())
        datos_validos = {**datos, "fin": date(2027, 3, 1)}
        self.assertTrue(model_admin.get_form(request)(datos_validos).is_valid())
        cambio = model_admin.get_form(request, self.miembros[0])(
            datos, instance=self.miembros[0]
        )
        self.assertNotIn("socio", cambio.fields)
        self.assertFalse(cambio.is_valid())
        self.assertIn("fecha final", str(cambio.errors).lower())
        datos["fin"] = date(2027, 3, 1)
        cambio_valido = model_admin.get_form(request, self.miembros[0])(
            datos, instance=self.miembros[0]
        )
        self.assertTrue(cambio_valido.is_valid(), cambio_valido.errors)
