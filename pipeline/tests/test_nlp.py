"""Pruebas de T-14 (NLP de quejas)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.src.nlp.clasificador import (  # noqa: E402
    cargar_quejas, dividir_por_texto_unico, entrenar_y_evaluar, textos_unicos,
)
from pipeline.src.nlp.similitud import precision_en_k  # noqa: E402
from pipeline.src.nlp.texto import normalizar, tokenizar  # noqa: E402


def test_normalizar_quita_acentos_y_conserva_enie():
    assert normalizar("¡Llevo DÍAS sin agua en la año!") == "llevo dias sin agua en la año"


@pytest.mark.parametrize("vacio", [None, "", "   ", "nan", "NaN"])
def test_normalizar_vacios_devuelve_cadena_vacia(vacio):
    assert normalizar(vacio) == ""


def test_tokenizar_conserva_negaciones():
    tokens = tokenizar("No hay agua, sin presión desde el lunes")
    assert "no" in tokens and "sin" in tokens
    assert "el" not in tokens and "desde" not in tokens


def test_division_por_texto_unico_sin_fuga():
    unicos = textos_unicos(cargar_quejas())
    entrena, prueba = dividir_por_texto_unico(unicos)
    assert not set(entrena["descripcion"]) & set(prueba["descripcion"])
    assert set(prueba["categoria"]) == set(unicos["categoria"])  # estratificado: todas las clases en prueba


def test_textos_con_dos_categorias_fallan():
    df = pd.DataFrame({"descripcion": ["a", "a"], "categoria": ["x", "y"], "prioridad": ["alta", "alta"]})
    with pytest.raises(ValueError):
        textos_unicos(df)


def test_precision_en_k_caso_conocido():
    base = np.eye(3)
    consulta = np.array([[1.0, 0.0, 0.0]])
    assert precision_en_k(consulta, base, ["a"], ["a", "b", "b"], k=1) == 1.0
    assert precision_en_k(consulta, base, ["a"], ["a", "b", "b"], k=3) == pytest.approx(1 / 3)


def test_modelo_reproducible_y_mejor_que_linea_base():
    r1, r2 = entrenar_y_evaluar(), entrenar_y_evaluar()
    assert r1.metricas[0]["f1_macro"] == r2.metricas[0]["f1_macro"]  # semilla 42
    principal, base = r1.metricas[0], r1.metricas[2]
    assert principal["f1_macro"] > base["f1_macro"]
