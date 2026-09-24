"""Pruebas de T-08."""
import pytest

from pipeline.src.data.limpieza import ejecutar as limpiar
from pipeline.src.ml.segmentos import VARIABLES, por_toma
from pipeline.src.config import COLUMNAS_PROHIBIDAS


def test_variables_por_toma_sin_fuga():
    tablas, _ = limpiar()
    t = por_toma(tablas["dataset"])
    assert len(t) == 480 and not t[VARIABLES].isna().any().any()
    assert not set(VARIABLES) & COLUMNAS_PROHIBIDAS


def test_mlp_forma_de_salida():
    torch = pytest.importorskip("torch")
    from pipeline.src.deep_learning.mlp import MLP
    assert MLP(10)(torch.zeros(4, 10)).shape == (4,)
