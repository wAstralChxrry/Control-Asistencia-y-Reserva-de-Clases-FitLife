from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from gimnasio import demo, panel_views, perfil, reserva_admin_views, views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ingresar/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.inicio, name="inicio"),
    path("demo/cargar/", demo.cargar_demo, name="cargar_demo"),
    path("demo/eliminar/", demo.eliminar_demo, name="eliminar_demo"),
    path("demo/acceso/", demo.credenciales_demo, name="credenciales_demo"),
    path(
        "gestion/reservas/", reserva_admin_views.reservas_admin, name="reservas_admin"
    ),
    path(
        "gestion/reservas/nuevo/",
        reserva_admin_views.reserva_admin_crear,
        name="reserva_admin_crear",
    ),
    path(
        "gestion/reservas/<int:pk>/editar/",
        reserva_admin_views.reserva_admin_editar,
        name="reserva_admin_editar",
    ),
    path(
        "gestion/reservas/<int:pk>/eliminar/",
        reserva_admin_views.reserva_admin_eliminar,
        name="reserva_admin_eliminar",
    ),
    path("gestion/<str:recurso>/", views.lista, name="lista"),
    path("gestion/<str:recurso>/nuevo/", views.editar, name="crear"),
    path("gestion/<str:recurso>/<int:pk>/editar/", views.editar, name="editar"),
    path("gestion/<str:recurso>/<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("acceso/", views.acceso, name="acceso"),
    path("aforo/", views.aforo, name="aforo"),
    path("mi-qr/", views.qr, name="qr"),
    path("mis-datos/", perfil.editar_perfil, name="perfil"),
    path("mis-datos/contrasena/", perfil.cambiar_contrasena, name="cambiar_contrasena"),
    path(
        "gestion/clases/<int:pk>/participantes/",
        panel_views.participantes_clase,
        name="participantes_clase",
    ),
    path("clases/<int:pk>/reservar/", views.reservar, name="reservar"),
    path("reservas/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
]
