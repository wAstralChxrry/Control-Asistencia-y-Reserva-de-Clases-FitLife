"""Cálculos de vigencia de las membresías."""

from calendar import monthrange
from datetime import date, timedelta


def fecha_fin_membresia(inicio, meses):
    """Devuelve el último día incluido antes del aniversario del plan."""
    numero_mes = inicio.year * 12 + inicio.month - 1 + meses
    ano, mes_cero = divmod(numero_mes, 12)
    mes = mes_cero + 1
    dia = min(inicio.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia) - timedelta(days=1)
