import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(0)]
    )
    duracion_dias = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )

    def __str__(self):
        return self.nombre


class Membresia(models.Model):
    socio = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    inicio = models.DateField()
    fin = models.DateField()
    estado = models.CharField(
        max_length=12,
        choices=[
            ("activa", "Activa"),
            ("vencida", "Vencida"),
            ("congelada", "Congelada"),
        ],
        default="activa",
    )
    codigo = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dentro = models.BooleanField(default=False)

    @property
    def vigente(self):
        return (
            self.estado == "activa" and self.inicio <= timezone.localdate() <= self.fin
        )

    @property
    def estado_visible(self):
        return dict(self._meta.get_field("estado").choices)[self.estado_efectivo]

    @property
    def estado_efectivo(self):
        if self.estado == "activa" and self.fin < timezone.localdate():
            return "vencida"
        return self.estado

    @property
    def permite_acceso(self):
        return self.vigente and self.socio.is_active

    def __str__(self):
        return str(self.socio)


class Pago(models.Model):
    membresia = models.ForeignKey(Membresia, on_delete=models.PROTECT)
    monto = models.DecimalField(
        max_digits=10, decimal_places=0, validators=[MinValueValidator(0)]
    )
    fecha = models.DateField(default=timezone.localdate)
    detalle = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.membresia}: {self.monto}"


class Clase(models.Model):
    nombre = models.CharField(max_length=100)
    inicio = models.DateTimeField()
    cupos = models.PositiveIntegerField()

    def __str__(self):
        inicio = (
            timezone.localtime(self.inicio)
            if timezone.is_aware(self.inicio)
            else self.inicio
        )
        return f"{self.nombre} - {inicio:%d/%m/%Y %H:%M}"


class Reserva(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="reservas")
    socio = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    espera = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clase", "socio"], name="reserva_unica")
        ]
        ordering = ["creada", "pk"]


class Acceso(models.Model):
    membresia = models.ForeignKey(Membresia, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(
        max_length=10, choices=[("entrada", "Entrada"), ("salida", "Salida")]
    )
    permitido = models.BooleanField()
    detalle = models.CharField(max_length=200, blank=True)


class LoteDemo(models.Model):
    """Identificadores de los registros generados para una demostración."""

    registros = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)
