from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .forms import ClaseForm, MembresiaForm, PagoForm, PlanForm
from .models import Acceso, Clase, Membresia, Pago, Plan, Reserva
from .servicios import promover_lista_espera, reconciliar_esperas

admin.site.site_header = "Administración FitLife"
admin.site.site_title = "FitLife"
admin.site.index_title = "Gestión del gimnasio"


Usuario = get_user_model()
admin.site.unregister(Usuario)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        reconciliar_esperas(obj.pk)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanForm
    list_display = ("nombre", "precio", "duracion_dias")
    search_fields = ("nombre",)
    list_filter = ("duracion_dias",)


class EstadoEfectivoFilter(admin.SimpleListFilter):
    title = "estado"
    parameter_name = "estado_efectivo"

    def lookups(self, request, model_admin):
        return (
            ("activa", "Activa"),
            ("vencida", "Vencida"),
            ("congelada", "Congelada"),
        )

    def queryset(self, request, queryset):
        hoy = timezone.localdate()
        if self.value() == "activa":
            return queryset.filter(estado="activa", fin__gte=hoy)
        if self.value() == "vencida":
            return queryset.filter(
                Q(estado="vencida") | Q(estado="activa", fin__lt=hoy)
            )
        if self.value() == "congelada":
            return queryset.filter(estado="congelada")
        return queryset


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    form = MembresiaForm
    list_display = ("socio", "plan", "estado_mostrado", "inicio", "fin", "dentro")
    list_filter = (EstadoEfectivoFilter, "plan", "dentro")
    search_fields = ("socio__username", "socio__first_name", "socio__last_name")
    readonly_fields = ("codigo", "dentro")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "socio") if obj else fields

    @admin.display(description="Estado", ordering="estado")
    def estado_mostrado(self, obj):
        return obj.estado_visible

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        reconciliar_esperas(obj.socio_id)


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    form = PagoForm
    list_display = ("membresia", "monto", "fecha")
    list_filter = ("fecha",)
    search_fields = ("membresia__socio__username",)


@admin.register(Clase)
class ClaseAdmin(admin.ModelAdmin):
    form = ClaseForm
    list_display = ("nombre", "inicio", "cupos")
    list_filter = ("inicio",)
    search_fields = ("nombre",)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # Se adquiere el mismo bloqueo que usan las reservas antes de validar cupos.
        with transaction.atomic():
            if request.method == "POST" and object_id:
                Clase.objects.select_for_update().filter(pk=object_id).first()
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        promover_lista_espera(obj)


class SoloLecturaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reserva)
class ReservaAdmin(SoloLecturaAdmin):
    list_display = ("clase", "socio", "espera", "creada")
    list_filter = ("espera", "clase")
    search_fields = ("socio__username", "clase__nombre")


@admin.register(Acceso)
class AccesoAdmin(SoloLecturaAdmin):
    list_display = ("membresia", "fecha", "tipo", "permitido")
    list_filter = ("tipo", "permitido", "fecha")
    search_fields = ("membresia__socio__username",)
    readonly_fields = ("fecha",)
