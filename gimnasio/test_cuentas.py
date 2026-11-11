from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .forms import MembresiaForm, PagoForm, PlanForm, SocioForm
from .models import Membresia, Plan


class SocioFormTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="laura", password="MontanaSeguro!2026", email="laura@example.org"
        )

    def datos(self, **changes):
        datos = {
            "username": "laura",
            "first_name": "Laura",
            "last_name": "Diaz",
            "email": "laura@example.org",
            "password": "",
            "is_active": "on",
        }
        datos.update(changes)
        return datos

    def test_editar_sin_clave_conserva_hash(self):
        hash_original = self.usuario.password
        form = SocioForm(self.datos(), instance=self.usuario)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.password, hash_original)
        self.assertTrue(self.usuario.check_password("MontanaSeguro!2026"))

    def test_crear_requiere_clave(self):
        form = SocioForm(self.datos(username="nueva"))
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_validadores_rechazan_claves_debiles(self):
        form = SocioForm(self.datos(password="123"), instance=self.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_cambiar_clave_la_guarda_cifrada(self):
        form = SocioForm(
            self.datos(password="ArbolesAzules!2026"), instance=self.usuario
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("ArbolesAzules!2026"))


class ValidacionesTest(TestCase):
    def test_membresia_form_admite_campo_socio_excluido_por_admin(self):
        from django.forms import modelform_factory

        form_class = modelform_factory(
            Membresia, form=MembresiaForm, fields=["plan", "inicio", "fin", "estado"]
        )
        self.assertNotIn("socio", form_class().fields)

    def test_no_reasigna_socio_de_una_membresia(self):
        titular = User.objects.create_user(username="titular")
        otro = User.objects.create_user(username="otro")
        plan = Plan.objects.create(nombre="Mensual", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        membresia = Membresia.objects.create(
            socio=titular, plan=plan, inicio=hoy, fin=hoy
        )
        form = MembresiaForm(
            {
                "socio": otro.pk,
                "plan": plan.pk,
                "inicio": hoy,
                "fin": hoy,
                "estado": "activa",
            },
            instance=membresia,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        membresia.refresh_from_db()
        self.assertEqual(membresia.socio_id, titular.pk)

    def test_nueva_membresia_excluye_administradores(self):
        admin = User.objects.create_user(username="admin", is_staff=True)
        self.assertFalse(
            MembresiaForm().fields["socio"].queryset.filter(pk=admin.pk).exists()
        )

    def test_plan_rechaza_precio_negativo_y_duracion_cero(self):
        form = PlanForm({"nombre": "Mensual", "precio": -1, "duracion_dias": 0})
        self.assertFalse(form.is_valid())
        self.assertIn("precio", form.errors)
        self.assertIn("duracion_dias", form.errors)

    def test_pago_rechaza_monto_negativo(self):
        user = User.objects.create_user(username="socio")
        plan = Plan.objects.create(nombre="Mensual", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        membresia = Membresia.objects.create(socio=user, plan=plan, inicio=hoy, fin=hoy)
        form = PagoForm({"membresia": membresia.pk, "monto": -1, "fecha": hoy})
        self.assertFalse(form.is_valid())
        self.assertIn("monto", form.errors)

    def test_estado_efectivo_y_cuenta_inactiva(self):
        user = User.objects.create_user(username="socio")
        plan = Plan.objects.create(nombre="Mensual", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        membresia = Membresia.objects.create(
            socio=user,
            plan=plan,
            inicio=hoy - timedelta(days=10),
            fin=hoy - timedelta(days=1),
        )
        self.assertEqual(membresia.estado_efectivo, "vencida")
        self.assertEqual(membresia.estado_visible, "Vencida")
        membresia.fin = hoy + timedelta(days=1)
        self.assertTrue(membresia.permite_acceso)
        user.is_active = False
        self.assertFalse(membresia.permite_acceso)
