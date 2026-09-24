"""Pruebas de T-05 y T-07 (rápidas: no entrenan los modelos completos)."""
import numpy as np
import pandas as pd

from pipeline.src.config import COLUMNAS_PROHIBIDAS
from pipeline.src.data.limpieza import ejecutar as limpiar
from pipeline.src.data.publicar import validar
from pipeline.src.features.variables import BINARIAS, CATEGORICAS, NUMERICAS, construir
from pipeline.src.ml.modelos import cortes_temporales
from pipeline.src.preprocessing.eda import caja, wilson


def test_caja_cuartiles():
    c = caja(pd.Series([1, 2, 3, 4, 100.0]), "x")
    assert c["mediana"] == 3 and c["q1"] == 2 and c["q3"] == 4 and c["atipicos"] == [100.0]


def test_wilson_contiene_proporcion():
    lo, hi = wilson(25, 100)
    assert lo < 0.25 < hi and 0 <= lo and hi <= 1


def test_variables_sin_fuga():
    assert not set(NUMERICAS + BINARIAS + CATEGORICAS) & COLUMNAS_PROHIBIDAS
    tablas, _ = limpiar()
    df = construir(tablas["dataset"])
    # el historial de la primera factura de cada toma no puede conocer su propia etiqueta
    primeras = df.sort_values("periodo").groupby("id_toma").head(1)
    assert primeras["tasa_tardio_historica"].isna().all()


def test_cv_temporal_no_mira_el_futuro():
    per = pd.Series(np.repeat([f"2025-{m:02d}" for m in range(1, 13)], 3))
    for tr, va in cortes_temporales(per):
        assert per.iloc[tr].max() < per.iloc[va].min()


def test_payload_minimo():
    validar({"tipo": "tabla", "titulo": "t", "conclusion": "c", "fuente": "f"})
