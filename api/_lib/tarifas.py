"""Cálculo del importe de un recibo con el tarifario CEA Querétaro.

Portado de Operaguas (Odoo): recibo/models/tarifa.py (importe_agua) y
recibo/models/recibo.py (_generar_linea_consumo, _compute_subtotal_iva).
Dueño: Claude-E (T-03). Contrato: docs/CONTRATOS.md §5.

Reglas:
1. El consumo se factura redondeado al entero con redondeo tradicional
   (medio hacia arriba: 5.5 → 6, 5.4 → 5).
2. El importe de agua sale de la tabla CEA por tipo de tarifa y m³ del
   periodo. Si el consumo excede la tabla, se usa el m³ más alto disponible.
3. Cargo = agua + 10 % si la toma tiene alcantarillado + 12 % si tiene
   saneamiento, redondeado a 2 decimales (igual que Odoo).
4. IVA 16 % sobre el subtotal solo en tarifas NO domésticas; el agua de uso
   doméstico va a tasa 0 % (LIVA 2-A II h).

Función pura: sin red y sin dependencias fuera de la biblioteca estándar.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

ARCHIVO_TARIFAS = Path(__file__).with_name("tarifas_cea.csv")
PERIODO_VIGENTE = "2026-T3"

TARIFAS_DOMESTICAS = {
    "domestico_apoyo", "domestico_economico", "domestico_medio",
    "domestico_alto", "domestico_rural",
}
TASA_ALCANTARILLADO = 0.10
TASA_SANEAMIENTO = 0.12
TASA_IVA = 0.16


@lru_cache(maxsize=1)
def _tabla() -> dict[tuple[str, str], dict[int, float]]:
    """Lee el tarifario una sola vez: {(periodo, tipo): {m3: importe}}."""
    tabla: dict[tuple[str, str], dict[int, float]] = {}
    with ARCHIVO_TARIFAS.open(encoding="utf-8") as fh:
        for fila in csv.DictReader(fh):
            clave = (fila["periodo"], fila["tipo_tarifa"])
            tabla.setdefault(clave, {})[int(fila["consumo_m3"])] = float(fila["importe_agua"])
    return tabla


def tipos_de_tarifa(periodo: str = PERIODO_VIGENTE) -> list[str]:
    """Tipos de tarifa disponibles en un periodo."""
    return sorted(t for p, t in _tabla() if p == periodo)


def redondear_consumo(consumo_m3: float) -> int:
    """Redondeo tradicional (medio hacia arriba), no el bancario de round()."""
    return int(math.floor((consumo_m3 or 0.0) + 0.5))


def importe_agua(tipo_tarifa: str, consumo_m3: float, periodo: str = PERIODO_VIGENTE) -> float:
    """Importe de agua potable de la tabla CEA para un consumo."""
    filas = _tabla().get((periodo, tipo_tarifa))
    if not filas:
        raise ValueError(
            f"No hay tarifa '{tipo_tarifa}' en el periodo {periodo}. "
            f"Tipos válidos: {', '.join(tipos_de_tarifa(periodo))}"
        )
    m3 = redondear_consumo(consumo_m3)
    if m3 in filas:
        return filas[m3]
    return filas[max(filas)]  # excede la tabla: se usa el m³ más alto


def calcular_importe(
    tipo_tarifa: str,
    consumo_m3: float,
    alcantarillado: bool,
    saneamiento: bool,
    periodo: str = PERIODO_VIGENTE,
) -> dict:
    """Desglose del recibo. Firma congelada en docs/CONTRATOS.md §5.

    Devuelve: consumo_facturado (m³ enteros), agua, alcantarillado,
    saneamiento, subtotal, iva, total. `subtotal` se calcula como Odoo
    (redondeo del cargo completo), por eso puede diferir un centavo de la
    suma de los conceptos mostrados.
    """
    if consumo_m3 is None or consumo_m3 < 0:
        raise ValueError("El consumo debe ser un número mayor o igual a 0.")

    agua = round(importe_agua(tipo_tarifa, consumo_m3, periodo), 2)
    cargo = agua
    if alcantarillado:
        cargo += agua * TASA_ALCANTARILLADO
    if saneamiento:
        cargo += agua * TASA_SANEAMIENTO
    subtotal = round(cargo, 2)
    iva = 0.0 if tipo_tarifa in TARIFAS_DOMESTICAS else round(subtotal * TASA_IVA, 2)

    return {
        "periodo": periodo,
        "tipo_tarifa": tipo_tarifa,
        "consumo_facturado": redondear_consumo(consumo_m3),
        "agua": agua,
        "alcantarillado": round(agua * TASA_ALCANTARILLADO, 2) if alcantarillado else 0.0,
        "saneamiento": round(agua * TASA_SANEAMIENTO, 2) if saneamiento else 0.0,
        "subtotal": subtotal,
        "iva": iva,
        "total": round(subtotal + iva, 2),
    }
