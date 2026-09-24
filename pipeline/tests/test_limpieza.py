"""Pruebas de T-04 (pipeline de datos). Corren con: pytest pipeline/tests -q"""
import pandas as pd
import pytest

from pipeline.src.config import COLUMNAS_PROHIBIDAS, FECHA_CORTE
from pipeline.src.data.limpieza import ejecutar, periodo_tarifario


@pytest.fixture(scope="module")
def salida():
    return ejecutar()


def test_sin_duplicados_en_lecturas(salida):
    tablas, _ = salida
    assert not tablas["lecturas"].duplicated(["id_toma", "periodo"]).any()


def test_una_fila_por_toma_y_periodo(salida):
    tablas, _ = salida
    ds = tablas["dataset"]
    assert len(ds) == 480 * 30
    assert not ds.duplicated(["id_toma", "periodo"]).any()


def test_parametros_del_generador_no_salen(salida):
    tablas, _ = salida
    for nombre in ("tomas", "dataset"):
        assert not {"consumo_base", "propension_mora"} & set(tablas[nombre].columns)


def test_censura(salida):
    tablas, _ = salida
    r = tablas["recibos"]
    corte = pd.Timestamp(FECHA_CORTE)
    fuera = r[r["fecha_vencimiento"] > corte]
    assert (~fuera["en_entrenamiento"]).all()
    assert fuera["pago_tardio"].isna().all()
    dentro = r[r["en_entrenamiento"]]
    assert dentro["pago_tardio"].notna().all()           # todo recibo vencido tiene etiqueta
    vencido_sin_pago = dentro[~dentro["pagado"]]
    assert vencido_sin_pago["pago_tardio"].all()         # vencido y sin pagar = tardío


def test_importes_consistentes(salida):
    tablas, _ = salida
    r = tablas["recibos"]
    suma = (r["importe_agua"] + r["importe_alcantarillado"] + r["importe_saneamiento"] + r["iva"]).round(2)
    assert (abs(suma - r["total_pagar"]) <= 0.02).all()
    domesticos = r[r["tipo_tarifa"] == "domestico"]
    assert (domesticos["iva"] == 0).all()                # agua doméstica a tasa 0 %


def test_periodo_tarifario():
    assert periodo_tarifario("2024-04") == "2026-T2"
    assert periodo_tarifario("2026-07") == "2026-T3"


def test_prohibidas_declaradas():
    assert {"fecha_pago", "dias_atraso", "pagado", "tiene_fuga"} <= COLUMNAS_PROHIBIDAS
