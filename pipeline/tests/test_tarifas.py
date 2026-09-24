"""Pruebas de api/_lib/tarifas.py contra el tarifario CEA 2026-T3 (T-03)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api._lib.tarifas import calcular_importe, importe_agua, redondear_consumo, tipos_de_tarifa  # noqa: E402


def test_once_tipos_en_el_periodo_vigente():
    assert len(tipos_de_tarifa()) == 11


def test_redondeo_tradicional():
    assert redondear_consumo(5.5) == 6
    assert redondear_consumo(5.4) == 5
    assert redondear_consumo(2.5) == 3  # round() bancario daría 2


def test_importe_cero_m3_domestico_medio():
    assert importe_agua("domestico_medio", 0) == 228.08


def test_consumo_mayor_a_la_tabla_usa_el_ultimo_m3():
    assert importe_agua("comercial", 500) == importe_agua("comercial", 59)


def test_domestico_sin_iva_y_con_recargos():
    r = calcular_importe("domestico_medio", 0, alcantarillado=True, saneamiento=True)
    assert r["iva"] == 0.0
    assert r["subtotal"] == round(228.08 * 1.22, 2)
    assert r["total"] == r["subtotal"]


def test_no_domestico_paga_iva():
    r = calcular_importe("comercial", 20, alcantarillado=False, saneamiento=False)
    assert r["iva"] == round(r["subtotal"] * 0.16, 2)
    assert r["total"] == round(r["subtotal"] + r["iva"], 2)


def test_errores_claros():
    with pytest.raises(ValueError):
        calcular_importe("inexistente", 10, True, True)
    with pytest.raises(ValueError):
        calcular_importe("domestico_medio", -1, True, True)
