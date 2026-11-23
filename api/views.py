import qrcode

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from rest_framework.generics import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from gimnasio.models import Acceso, Clase, Membresia, Pago, Plan, Reserva
from gimnasio.servicios import promover_lista_espera, reconciliar_esperas
from .permissions import EsAdministrador
from .serializers import (
    ClaseSerializer,
    MembresiaSerializer,
    PagoSerializer,
    PlanSerializer,
    ReservaSerializer,
    SocioSerializer,
    AccesoSerializer,
    PerfilSerializer,
)


class AdminViewSet(viewsets.ModelViewSet):
    permission_classes = [EsAdministrador]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "No se puede eliminar porque tiene registros asociados."
            )


class SocioViewSet(AdminViewSet):
    queryset = get_user_model().objects.filter(is_staff=False).order_by("pk")
    serializer_class = SocioSerializer

    def perform_update(self, serializer):
        with transaction.atomic():
            usuario = serializer.save()
            reconciliar_esperas(usuario.pk)


class PlanViewSet(AdminViewSet):
    queryset = Plan.objects.all().order_by("pk")
    serializer_class = PlanSerializer


class MembresiaViewSet(AdminViewSet):
    queryset = Membresia.objects.select_related("socio", "plan").order_by("pk")
    serializer_class = MembresiaSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            miembro = serializer.save()
            reconciliar_esperas(miembro.socio_id)

    def perform_update(self, serializer):
        with transaction.atomic():
            miembro = serializer.save()
            reconciliar_esperas(miembro.socio_id)


class PagoViewSet(AdminViewSet):
    queryset = Pago.objects.all().order_by("pk")
    serializer_class = PagoSerializer


class ClaseViewSet(viewsets.ModelViewSet):
    queryset = Clase.objects.annotate(
        confirmadas=Count("reservas", filter=Q(reservas__espera=False))
    ).order_by("inicio", "pk")
    serializer_class = ClaseSerializer

    def get_permissions(self):
        return (
            [IsAuthenticated()]
            if self.action in ("list", "retrieve")
            else [EsAdministrador()]
        )

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            clase = get_object_or_404(
                Clase.objects.select_for_update(), pk=kwargs["pk"]
            )
            serializer = self.get_serializer(
                clase, data=request.data, partial=kwargs.pop("partial", False)
            )
            serializer.is_valid(raise_exception=True)
            if (
                serializer.validated_data.get("cupos", clase.cupos)
                < clase.reservas.filter(espera=False).count()
            ):
                raise ValidationError(
                    {"cupos": "Hay más reservas confirmadas que cupos."}
                )
            serializer.save()
            promover_lista_espera(clase)
            return Response(serializer.data)


class ReservaViewSet(viewsets.ModelViewSet):
    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Reserva.objects.select_related("clase", "socio")
        return qs if self.request.user.is_staff else qs.filter(socio=self.request.user)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [EsAdministrador()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            clase = get_object_or_404(
                Clase.objects.select_for_update(),
                pk=serializer.validated_data["clase"].pk,
            )
            socio = serializer.validated_data["socio"]
            miembro = Membresia.objects.filter(socio=socio).first()
            if (
                socio.is_staff
                or not miembro
                or not miembro.permite_acceso
                or clase.inicio <= timezone.now()
            ):
                raise ValidationError(
                    "Se requiere un socio habilitado y una clase futura."
                )
            if Reserva.objects.filter(clase=clase, socio=socio).exists():
                raise ValidationError("El socio ya está inscrito en esta clase.")
            reserva = serializer.save(espera=True)
            promover_lista_espera(clase)
            reserva.refresh_from_db()
        return Response(
            self.get_serializer(reserva).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        original = self.get_object()
        serializer = self.get_serializer(
            original, data=request.data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        clase_id = serializer.validated_data.get("clase", original.clase).pk
        socio = serializer.validated_data.get("socio", original.socio)
        with transaction.atomic():
            clases = {
                c.pk: c
                for c in Clase.objects.select_for_update()
                .filter(pk__in={original.clase_id, clase_id})
                .order_by("pk")
            }
            actual = get_object_or_404(Reserva, pk=original.pk)
            if (actual.clase_id, actual.socio_id) != (
                original.clase_id,
                original.socio_id,
            ):
                raise ValidationError("La reserva cambió; vuelve a intentarlo.")
            destino = clases[clase_id]
            miembro = Membresia.objects.filter(socio=socio).first()
            if (
                socio.is_staff
                or not miembro
                or not miembro.permite_acceso
                or destino.inicio <= timezone.now()
            ):
                raise ValidationError(
                    "Se requiere un socio habilitado y una clase futura."
                )
            if (
                Reserva.objects.filter(clase=destino, socio=socio)
                .exclude(pk=actual.pk)
                .exists()
            ):
                raise ValidationError("El socio ya está inscrito en esta clase.")
            if (actual.clase_id, actual.socio_id) != (clase_id, socio.pk):
                origen = clases[actual.clase_id]
                actual.clase, actual.socio, actual.espera, actual.creada = (
                    destino,
                    socio,
                    True,
                    timezone.now(),
                )
                actual.save(update_fields=["clase", "socio", "espera", "creada"])
                if origen.pk != destino.pk:
                    promover_lista_espera(origen)
                promover_lista_espera(destino)
                actual.refresh_from_db()
        return Response(self.get_serializer(actual).data)

    def destroy(self, request, *args, **kwargs):
        original = self.get_object()
        with transaction.atomic():
            clase = get_object_or_404(
                Clase.objects.select_for_update(), pk=original.clase_id
            )
            reserva = get_object_or_404(Reserva, pk=original.pk, clase=clase)
            reserva.delete()
            promover_lista_espera(clase)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def reservar(self, request):
        if request.user.is_staff:
            raise ValidationError("La reserva de socio requiere una cuenta de socio.")
        try:
            clase_id = int(request.data.get("clase"))
        except (TypeError, ValueError):
            raise ValidationError({"clase": "Indica un identificador válido."})
        with transaction.atomic():
            clase = get_object_or_404(Clase.objects.select_for_update(), pk=clase_id)
            miembro = Membresia.objects.filter(socio=request.user).first()
            if (
                not miembro
                or not miembro.permite_acceso
                or clase.inicio <= timezone.now()
            ):
                raise ValidationError(
                    "Necesitas una membresía vigente y una clase futura."
                )
            if Reserva.objects.filter(clase=clase, socio=request.user).exists():
                raise ValidationError("Ya tienes una inscripción para esta clase.")
            promover_lista_espera(clase)
            reserva = Reserva.objects.create(
                clase=clase,
                socio=request.user,
                espera=clase.reservas.filter(espera=False).count() >= clase.cupos,
            )
        return Response(
            self.get_serializer(reserva).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        if request.user.is_staff:
            raise ValidationError(
                "La cancelación de socio requiere una cuenta de socio."
            )
        with transaction.atomic():
            reserva = get_object_or_404(Reserva, pk=pk, socio=request.user)
            clase = get_object_or_404(
                Clase.objects.select_for_update(), pk=reserva.clase_id
            )
            reserva = get_object_or_404(Reserva, pk=pk, socio=request.user, clase=clase)
            reserva.delete()
            promover_lista_espera(clase)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def mi_cuenta(request):
    if request.method == "PATCH":
        if request.user.is_staff:
            raise ValidationError("Esta función corresponde a cuentas de socio.")
        serializer = PerfilSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    return Response(
        {
            "id": request.user.pk,
            "usuario": request.user.username,
            "nombre": request.user.first_name,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "administrador": request.user.is_staff,
        }
    )


@api_view(["GET"])
@permission_classes([EsAdministrador])
def aforo(request):
    return Response({"aforo": Membresia.objects.filter(dentro=True).count()})


@api_view(["POST"])
@permission_classes([EsAdministrador])
def registrar_acceso(request):
    serializer = AccesoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        miembro = get_object_or_404(
            Membresia.objects.select_for_update(),
            codigo=serializer.validated_data["codigo"],
        )
        tipo = serializer.validated_data["tipo"]
        permitido = (
            (miembro.permite_acceso and not miembro.dentro)
            if tipo == "entrada"
            else miembro.dentro
        )
        detalle = (
            "Movimiento registrado."
            if permitido
            else "Membresía no vigente o movimiento duplicado."
        )
        if permitido:
            miembro.dentro = tipo == "entrada"
            miembro.save(update_fields=["dentro"])
        Acceso.objects.create(
            membresia=miembro, tipo=tipo, permitido=permitido, detalle=detalle
        )
    return Response({"permitido": permitido, "detalle": detalle})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mi_membresia(request):
    if request.user.is_staff:
        raise ValidationError("Esta función corresponde a cuentas de socio.")
    miembro = get_object_or_404(Membresia, socio=request.user)
    return Response(MembresiaSerializer(miembro).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mi_qr(request):
    if request.user.is_staff:
        raise ValidationError("Esta función corresponde a cuentas de socio.")
    miembro = get_object_or_404(Membresia, socio=request.user)
    response = HttpResponse(content_type="image/png")
    qrcode.make(str(miembro.codigo)).save(response, "PNG")
    response["Cache-Control"] = "no-store"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cambiar_contrasena(request):
    if request.user.is_staff:
        raise ValidationError("Esta función corresponde a cuentas de socio.")
    form = PasswordChangeForm(request.user, request.data)
    if not form.is_valid():
        raise ValidationError(dict(form.errors))
    form.save()
    return Response({"detalle": "Contraseña actualizada."})


@api_view(["GET"])
@permission_classes([EsAdministrador])
def resumen(request):
    accesos = Acceso.objects.select_related("membresia__socio").order_by("-fecha")[:8]
    return Response(
        {
            "aforo": Membresia.objects.filter(dentro=True).count(),
            "socios": get_user_model().objects.filter(is_staff=False).count(),
            "pagos": Pago.objects.count(),
            "clases": ClaseSerializer(
                Clase.objects.annotate(
                    confirmadas=Count("reservas", filter=Q(reservas__espera=False))
                )
                .filter(inicio__gte=timezone.now())
                .order_by("inicio")[:5],
                many=True,
            ).data,
            "accesos": [
                {
                    "socio": a.membresia.socio.get_full_name()
                    or a.membresia.socio.username,
                    "tipo": a.tipo,
                    "permitido": a.permitido,
                    "fecha": a.fecha,
                }
                for a in accesos
            ],
        }
    )
