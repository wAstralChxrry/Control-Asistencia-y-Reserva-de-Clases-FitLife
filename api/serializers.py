from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import serializers
from gimnasio.fechas import fecha_fin_membresia
from gimnasio.models import Clase, Membresia, Pago, Plan, Reserva


class SocioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "password",
        )

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Ingresa una contraseña."})
        if password:
            usuario = self.instance or get_user_model()()
            for campo in ("username", "first_name", "last_name", "email"):
                if campo in attrs:
                    setattr(usuario, campo, attrs[campo])
            validate_password(password, usuario)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return get_user_model().objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ("id", "nombre", "precio", "duracion_meses")


class MembresiaSerializer(serializers.ModelSerializer):
    fin = serializers.DateField(required=False)
    estado_visible = serializers.CharField(read_only=True)
    vigente = serializers.BooleanField(read_only=True)
    plan_nombre = serializers.CharField(source="plan.nombre", read_only=True)

    class Meta:
        model = Membresia
        fields = (
            "id",
            "socio",
            "plan",
            "plan_nombre",
            "inicio",
            "fin",
            "estado",
            "estado_visible",
            "vigente",
            "codigo",
            "dentro",
        )
        read_only_fields = ("codigo", "dentro")

    def validate(self, attrs):
        if self.instance is None and "fin" not in attrs:
            inicio = attrs.get("inicio")
            plan = attrs.get("plan")
            if inicio and plan:
                try:
                    attrs["fin"] = fecha_fin_membresia(inicio, plan.duracion_meses)
                except (OverflowError, ValueError):
                    raise serializers.ValidationError(
                        {"inicio": "La duración del plan excede las fechas permitidas."}
                    )
        inicio = attrs.get("inicio", getattr(self.instance, "inicio", None))
        fin = attrs.get("fin", getattr(self.instance, "fin", None))
        socio = attrs.get("socio", getattr(self.instance, "socio", None))
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError(
                {"fin": "La fecha final debe ser posterior al inicio."}
            )
        if socio and socio.is_staff:
            raise serializers.ValidationError({"socio": "Selecciona un socio."})
        if self.instance and socio and self.instance.socio_id != socio.pk:
            raise serializers.ValidationError(
                {"socio": "No se puede cambiar el titular."}
            )
        return attrs


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ("id", "membresia", "monto", "fecha", "detalle")


class ClaseSerializer(serializers.ModelSerializer):
    disponibles = serializers.SerializerMethodField()

    class Meta:
        model = Clase
        fields = ("id", "nombre", "inicio", "cupos", "disponibles")

    def get_disponibles(self, obj):
        confirmadas = getattr(obj, "confirmadas", None)
        if confirmadas is None:
            confirmadas = obj.reservas.filter(espera=False).count()
        return max(0, obj.cupos - confirmadas)

    def validate_cupos(self, value):
        if value < 1:
            raise serializers.ValidationError("La clase debe tener al menos un cupo.")
        return value


class ReservaSerializer(serializers.ModelSerializer):
    posicion = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = ("id", "clase", "socio", "espera", "creada", "posicion")
        read_only_fields = ("espera", "creada", "posicion")

    def get_posicion(self, obj):
        if not obj.espera:
            return None
        hoy = timezone.localdate()
        fecha_clase = timezone.localdate(obj.clase.inicio)
        elegibles = (
            Reserva.objects.filter(
                clase=obj.clase,
                espera=True,
                socio__is_active=True,
                socio__membresia__estado="activa",
                socio__membresia__inicio__lte=min(hoy, fecha_clase),
                socio__membresia__fin__gte=max(hoy, fecha_clase),
            )
            .annotate(
                conflicto_horario=Exists(
                    Reserva.objects.filter(
                        socio_id=OuterRef("socio_id"),
                        clase__inicio=obj.clase.inicio,
                        espera=False,
                    ).exclude(clase_id=obj.clase_id)
                )
            )
            .filter(conflicto_horario=False)
        )
        if not elegibles.filter(pk=obj.pk).exists():
            return None
        return elegibles.filter(
            Q(creada__lt=obj.creada) | Q(creada=obj.creada, pk__lte=obj.pk)
        ).count()


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "first_name", "last_name", "email")
        read_only_fields = ("id", "username")


class AccesoSerializer(serializers.Serializer):
    codigo = serializers.UUIDField()
    tipo = serializers.ChoiceField(choices=("entrada", "salida"))
