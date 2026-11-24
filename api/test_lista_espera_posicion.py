from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from api.serializers import ReservaSerializer
from gimnasio.models import Clase, Membresia, Plan, Reserva


class PosicionListaEsperaTests(TestCase):
    def test_no_cuenta_en_espera_a_quien_tiene_reserva_confirmada_simultanea(self):
        plan = Plan.objects.create(nombre="Prueba", precio=100, duracion_dias=30)
        hoy = timezone.localdate()
        primero = get_user_model().objects.create_user(username="primero")
        segundo = get_user_model().objects.create_user(username="segundo")
        for socio in (primero, segundo):
            Membresia.objects.create(
                socio=socio, plan=plan, inicio=hoy, fin=hoy + timedelta(days=30)
            )
        inicio = timezone.now() + timedelta(days=1)
        clase = Clase.objects.create(nombre="Yoga", inicio=inicio, cupos=1)
        simultanea = Clase.objects.create(nombre="Spinning", inicio=inicio, cupos=1)
        Reserva.objects.create(socio=primero, clase=simultanea, espera=False)
        espera_conflictiva = Reserva.objects.create(
            socio=primero, clase=clase, espera=True
        )
        espera_elegible = Reserva.objects.create(
            socio=segundo, clase=clase, espera=True
        )

        self.assertIsNone(ReservaSerializer(espera_conflictiva).data["posicion"])
        self.assertEqual(ReservaSerializer(espera_elegible).data["posicion"], 1)
