"""Controles administrativos de datos de demostración para la API."""

from django.utils.cache import patch_cache_control
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from gimnasio.demo import (
    DemoConfiguracionError,
    borrar_lote_demo,
    crear_lote_demo,
    generar_credenciales_demo,
)
from gimnasio.models import LoteDemo
from .permissions import EsAdministrador


@api_view(["GET"])
@permission_classes([EsAdministrador])
def estado(request):
    return Response({"cargada": LoteDemo.objects.filter(pk=1).exists()})


@api_view(["POST"])
@permission_classes([EsAdministrador])
def cargar(request):
    try:
        creado = crear_lote_demo()
    except DemoConfiguracionError as error:
        return Response(
            {"detalle": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return Response(
        {
            "detalle": (
                "Datos de demostración cargados."
                if creado
                else "Los datos de demostración ya están cargados."
            ),
            "cargada": True,
        },
        status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([EsAdministrador])
def eliminar(request):
    resultado = borrar_lote_demo()
    if resultado == "vinculados":
        return Response(
            {
                "detalle": "No se pueden eliminar los datos de demostración: hay registros añadidos posteriormente vinculados a ellos.",
                "cargada": True,
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {
            "detalle": (
                "Datos de demostración eliminados."
                if resultado == "eliminado"
                else "No hay datos de demostración cargados."
            ),
            "cargada": False,
        }
    )


@api_view(["POST"])
@permission_classes([EsAdministrador])
def acceso(request):
    try:
        datos, error = generar_credenciales_demo()
    except DemoConfiguracionError as error:
        return Response(
            {"detalle": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    if error:
        mensaje = (
            "Primero carga los datos de demostración."
            if error == "ausente"
            else "No hay un socio de demostración con membresía vigente."
        )
        return Response({"detalle": mensaje}, status=status.HTTP_400_BAD_REQUEST)
    respuesta = Response(
        {"detalle": "Credenciales de demostración generadas.", **datos}
    )
    patch_cache_control(respuesta, no_store=True, private=True)
    return respuesta
