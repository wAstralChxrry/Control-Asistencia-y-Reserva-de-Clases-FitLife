from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView
from . import demo, recursos
from .autenticacion import RenovacionView
from .views import (
    ClaseViewSet,
    MembresiaViewSet,
    PagoViewSet,
    PlanViewSet,
    ReservaViewSet,
    SocioViewSet,
    mi_cuenta,
    mi_membresia,
    aforo,
    registrar_acceso,
    mi_qr,
    resumen,
    cambiar_contrasena,
)

router = DefaultRouter()
router.register("socios", SocioViewSet)
router.register("planes", PlanViewSet)
router.register("membresias", MembresiaViewSet)
router.register("pagos", PagoViewSet)
router.register("clases", ClaseViewSet)
router.register("reservas", ReservaViewSet, basename="reserva")

urlpatterns = [
    path("recursos/favicon/", recursos.favicon, name="api_favicon"),
    path("demo/estado/", demo.estado, name="api_demo_estado"),
    path("demo/cargar/", demo.cargar, name="api_demo_cargar"),
    path("demo/eliminar/", demo.eliminar, name="api_demo_eliminar"),
    path("demo/acceso/", demo.acceso, name="api_demo_acceso"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RenovacionView.as_view(), name="token_refresh"),
    path("mi-cuenta/", mi_cuenta, name="api_mi_cuenta"),
    path("mi-membresia/", mi_membresia, name="api_mi_membresia"),
    path("mi-qr/", mi_qr, name="api_mi_qr"),
    path("mi-cuenta/contrasena/", cambiar_contrasena, name="api_cambiar_contrasena"),
    path("resumen/", resumen, name="api_resumen"),
    path("aforo/", aforo, name="api_aforo"),
    path("accesos/", registrar_acceso, name="api_accesos"),
    path("", include(router.urls)),
]
